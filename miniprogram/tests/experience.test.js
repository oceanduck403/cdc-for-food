const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { summarize, positiveFeedback } = require('../utils/checkin-state.js');

function page(name, api = {}, storage = {}) {
  let def;
  const calls = [];
  const wx = { getStorageSync: k => storage[k], setStorageSync: (k,v) => storage[k]=v,
    removeStorageSync: k => delete storage[k], switchTab: o => calls.push(o.url), reLaunch: o => calls.push(o.url),
    navigateTo: o => calls.push(o.url), showToast() {}, stopPullDownRefresh() {}, vibrateShort() {} };
  const sandbox = { Page: o => def=o, wx, console, getApp: () => ({}), setInterval: () => 1, clearInterval() {},
    require: name => name.includes('navigation') ? { open: wx.navigateTo, login: role => calls.push(role === 'admin' ? '/pages/admin-login/admin-login' : '/pages/login/login?role=' + (role || 'patient')) } : name.includes('auth') ? {getRole:()=>storage.role,getToken:()=>storage.token,isPrivacyAccepted:()=>true} : name.includes('admin.js') ? api : name.includes('appointments') ? api : name.includes('chat.js') ? api : name.includes('storage') ? {get:k=>storage[k],set:(k,v)=>storage[k]=v} : {} };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, `../pages/${name}/${name}.js`),'utf8'),sandbox);
  const p = {...def,data:JSON.parse(JSON.stringify(def.data))}; p.setData=o=>Object.assign(p.data,o);
  return {p,calls,storage};
}

test('用户登录直接进入带底栏的健康评估页',()=>{
  const {p,calls}=page('login');
  p._enterUserHome();
  assert.deepEqual(calls,['/pages/survey/survey']);
});
test('启动入口为登录页，仅恢复微信用户会话',()=>{
  const config=JSON.parse(fs.readFileSync(path.join(__dirname,'../app.json'),'utf8'));
  assert.equal(config.pages[0],'pages/login/login');
  const user=page('login',{}, {role:'patient',token:'valid-token'});user.p.onLoad({});
  assert.deepEqual(user.calls,['/pages/survey/survey']);
  for(const role of ['doctor','admin']) {
    const other=page('login',{}, {role,token:'valid-token'});other.p.onLoad({});assert.deepEqual(other.calls,[]);
  }
});
test('未登录的我的页面不伪造登录状态',()=>{
  const {p,storage}=page('mine'); p.onShow();
  assert.equal(p.data.isLogin,false); assert.equal(storage.token,undefined);
});

test('公开登录页不提供身份切换，退出清除会话并重建登录页',()=>{
  const root=path.join(__dirname,'..');
  for(const name of ['mine','admin']) {
    const markup=fs.readFileSync(path.join(root,`pages/${name}/${name}.wxml`),'utf8');
    assert.doesNotMatch(markup,/role-navigation|bindtap="goDoctor"|bindtap="goAdmin"|切换账号/);
  }
  const storage={token:'patient-token',role:'patient',profile:{id:1},userInfo:{id:1}};
  const app={globalData:{...storage}};const routes=[];
  const sandbox={module:{exports:{}},require:()=>({}),getApp:()=>app,wx:{removeStorageSync:k=>delete storage[k],reLaunch:o=>routes.push(o.url)}};
  vm.runInNewContext(fs.readFileSync(path.join(root,'utils/auth.js'),'utf8'),sandbox);
  sandbox.module.exports.logout();
  for(const key of ['token','role','profile','userInfo']) assert.equal(storage[key],undefined);
  assert.equal(app.globalData.token,'');assert.equal(app.globalData.role,'');
  assert.deepEqual(routes,['/pages/login/login']);
  const {p,calls}=page('login');p.onLoad({});
  assert.equal(p.switchRole,undefined);
  assert.deepEqual(calls,[]);
  const loginMarkup=fs.readFileSync(path.join(root,'pages/login/login.wxml'),'utf8');
  assert.doesNotMatch(loginMarkup,/医生端|管理员入口|医生登录/);
});

test('所有已注册页面的静态跳转目标均在页面清单中',()=>{
  const root=path.join(__dirname,'..');
  const config=JSON.parse(fs.readFileSync(path.join(root,'app.json'),'utf8'));
  const routes=new Set(config.pages.map(p=>'/'+p));
  for(const route of config.pages) for(const extension of ['.js','.wxml']) {
    const text=fs.readFileSync(path.join(root,route+extension),'utf8');
    for(const match of text.matchAll(/(?:['"`])(\/pages\/[a-z-]+\/[a-z-]+)/g)) {
      assert.ok(routes.has(match[1]),`${route}${extension} points to unregistered ${match[1]}`);
    }
  }
});

test('正式包不包含固定验证码、默认凭证或模拟支付入口',()=>{
  const root=path.join(__dirname,'..');
  const appConfig=JSON.parse(fs.readFileSync(path.join(root,'app.json'),'utf8'));
  const projectConfig=JSON.parse(fs.readFileSync(path.join(root,'project.config.json'),'utf8'));
  const sources=['pages/login/login.js','pages/login/login.wxml','pages/admin-login/admin-login.wxml',
    'pages/mine/mine.js','pages/mine/mine.wxml','pages/capture/capture.js','pages/capture/capture.wxml']
    .map(file=>fs.readFileSync(path.join(root,file),'utf8')).join('\n');
  assert.doesNotMatch(sources,/123456|admin123|手机号验证码登录|\/pages\/payment|开通会员|模拟支付/);
  assert.equal(appConfig.pages.includes('pages/payment/payment'),false);
  assert.equal(fs.existsSync(path.join(root,'pages/payment/payment.js')),false);
  assert.equal(fs.existsSync(path.join(root,'utils/payment.js')),false);
  assert.equal(projectConfig.setting.urlCheck,true);
  assert.equal(projectConfig.setting.uploadWithSourceMap,false);
  assert.ok(projectConfig.packOptions.ignore.some(item=>item.type==='folder'&&item.value==='tests'));
  for(const legacyPage of ['pages/gis-map','pages/knowledge']) {
    assert.ok(
      projectConfig.packOptions.ignore.some(item=>item.type==='folder'&&item.value===legacyPage),
      `legacy page ${legacyPage} must not enter the release package`,
    );
  }
});

test('旧账号请求返回401时不能清除新账号登录态',async()=>{
  const storage={token:'old-token',role:'patient'};let pending;
  const wx={getStorageSync:k=>storage[k],removeStorageSync:k=>delete storage[k],request:opts=>pending=opts};
  const sandbox={module:{exports:{}},require:name=>name.includes('transport')?{send:opts=>wx.request(opts),getDirectBaseUrl:()=> 'http://test'}:name.includes('config')?{apiBase:'http://test'}:{networkError:e=>e},wx};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../utils/api.js'),'utf8'),sandbox);
  const failed=sandbox.module.exports.request('/survey/my-responses');
  storage.token='doctor-token';storage.role='doctor';
  pending.success({statusCode:401,data:{detail:'expired'}});
  await assert.rejects(failed);assert.equal(storage.token,'doctor-token');assert.equal(storage.role,'doctor');
  const authFailed=sandbox.module.exports.request({url:'/auth/account-login',auth:false});
  pending.success({statusCode:401,data:{detail:'wrong password'}});
  await assert.rejects(authFailed);assert.equal(storage.token,'doctor-token');
});
test('同一天多项打卡只计一天，跨天重新开放，连续天数不中断',()=>{
  const records=[{day:'2026-09-12',type:'diet'},{day:'2026-09-12',type:'water'},{day:'2026-09-11',type:'diet'}];
  let state=summarize(records,new Date(2026,8,12));
  assert.equal(state.stats.totalDays,2);assert.equal(state.stats.totalActions,3);assert.equal(state.stats.continueDays,2);
  assert.equal(state.todayCheckin.diet,true);
  state=summarize(records,new Date(2026,8,13));assert.equal(state.todayCheckin.diet,false);assert.equal(state.stats.continueDays,2);
  assert.equal(summarize(records,new Date(2026,8,14)).stats.continueDays,0);
});
test('每日打卡即时点亮进度，近七天按天计数且不会因重复项目多算',()=>{
  const today=new Date(2026,8,15);
  const records=[
    {day:'2026-09-15',type:'diet'}, {day:'2026-09-15',type:'diet'},
    {day:'2026-09-15',type:'exercise'}, {day:'2026-09-14',type:'water'},
    {day:'2026-09-09',type:'diet'}, {day:'2026-09-08',type:'water'},
  ];
  const progress=positiveFeedback(records,today,'运动打卡已记录');
  assert.equal(progress.doneCount,2);
  assert.equal(progress.percent,67);
  assert.equal(progress.weekDays,3);
  assert.equal(progress.weekTrail.length,7);
  assert.equal(progress.weekTrail.at(-1).label,'今天');
  assert.equal(progress.weekTrail.at(-1).active,true);
  assert.equal(progress.lastAction,'运动打卡已记录');
  const complete=positiveFeedback([{day:'2026-09-15',type:'water'},...records],today);
  assert.equal(complete.doneCount,3);
  assert.equal(complete.percent,100);
  assert.match(complete.title,/3 件小事/);
});
