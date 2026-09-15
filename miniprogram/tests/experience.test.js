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

test('患者登录直接进入带底栏的主界面，医生保留工作台',()=>{
  const {p,calls}=page('login');
  p._navigateByRole('patient'); p._navigateByRole('doctor');
  assert.deepEqual(calls,['/pages/survey/survey','/pages/doctor/doctor']);
});
test('启动入口为登录页，已有会话恢复到对应身份主页',()=>{
  const config=JSON.parse(fs.readFileSync(path.join(__dirname,'../app.json'),'utf8'));
  assert.equal(config.pages[0],'pages/login/login');
  for(const [role,url] of [['patient','/pages/survey/survey'],['doctor','/pages/doctor/doctor'],['admin','/pages/admin/admin']]) {
    const {p,calls}=page('login',{}, {role,token:'valid-token'});p.onLoad({});assert.deepEqual(calls,[url]);
  }
});
test('未登录的我的页面不伪造登录状态',()=>{
  const {p,storage}=page('mine'); p.onShow();
  assert.equal(p.data.isLogin,false); assert.equal(storage.token,undefined);
});

test('身份切换只在初始登录流程提供，退出清除会话并重建登录页',()=>{
  const root=path.join(__dirname,'..');
  for(const name of ['mine','doctor','admin']) {
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
  const {p,calls}=page('login');p.onLoad({});assert.equal(p.data.currentRole,'patient');
  p.switchRole({currentTarget:{dataset:{role:'doctor'}}});assert.equal(p.data.currentRole,'doctor');
  p.switchRole({currentTarget:{dataset:{role:'admin'}}});assert.deepEqual(calls,['/pages/admin-login/admin-login']);
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
});

test('旧账号请求返回401时不能清除新账号登录态',async()=>{
  const storage={token:'old-token',role:'patient'};let pending;
  const sandbox={module:{exports:{}},require:()=>({apiBase:'http://test'}),wx:{getStorageSync:k=>storage[k],removeStorageSync:k=>delete storage[k],request:opts=>pending=opts}};
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
test('预约防重复点击，等待状态可见，改派后清除旧聊天，支持取消排队',async()=>{
  let resolveBook, booked=0, status={status:'waiting',assignment_id:null,doctor:null};
  const {p}=page('consult',{
    book:()=>{booked++;return new Promise(r=>resolveBook=r);},mine:async()=>status,
    cancel:async()=>{status={status:'cancelled',assignment_id:null,doctor:null};},
    fetchMessages:async()=>({messages:[]}),markRead:async()=>({}),
  });
  p._visible=true;p.setData({loggedIn:true});
  const first=p.bookAppointment();await p.bookAppointment();assert.equal(booked,1);
  resolveBook();await first;assert.equal(p.data.bookingStatus,'waiting');
  status={status:'assigned',assignment_id:9,doctor:{name:'医生'}};await p._init();assert.equal(p.data.assignmentId,9);
  p.data.messages=[{content:'旧会话'}];status={status:'waiting',assignment_id:null,doctor:null};await p._init();
  assert.equal(p.data.messages.length,0);await p.cancelAppointment();assert.equal(p.data.bookingStatus,'cancelled');
});
test('预约错误保留重试入口，不显示虚假成功',async()=>{
  const {p}=page('consult',{book:async()=>{throw Error('网络断开');}});
  p.setData({loggedIn:true});await p.bookAppointment();
  assert.equal(p.data.loadError,'网络断开');assert.equal(p.data.bookingBusy,false);assert.equal(p.data.bookingStatus,'none');
});

test('医生列表失败显示重试提示，恢复后生成可渲染的消息时间',async()=>{
  let fail=true;
  const {p}=page('doctor',{fetchDoctorPatients:async()=>{if(fail)throw Error('网络断开');return {patients:[{patient_id:1,last_message_at:'2026-09-12T10:00:00'}]}}},{token:'doctor-token',role:'doctor'});
  await p.loadPatients();assert.equal(p.data.loadError,'网络断开');assert.equal(p.data.loading,false);
  fail=false;await p.loadPatients();assert.equal(p.data.loadError,'');assert.equal(typeof p.data.patients[0].lastMessageTime,'string');
});
test('管理员聊天列表预处理时间，模板不调用页面方法',async()=>{
  const {p}=page('admin',{listChats:async()=>({messages:[{id:1,created_at:'2026-09-12T10:00:00'}]})});
  await p.loadChats();assert.ok(p.data.chats[0].displayTime);
  for(const name of ['doctor','admin']) {
    const markup=fs.readFileSync(path.join(__dirname,`../pages/${name}/${name}.wxml`),'utf8');
    assert.doesNotMatch(markup,/formatTime\(/);
  }
});
