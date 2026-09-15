const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.join(__dirname, '..');
function harness(file, ai, component = false) {
  let definition;
  const storage = { profile: { id: 7 }, token: 'session-7' };
  const navigation = [];
  const wx = { getStorageSync: k => storage[k], setStorageSync: (k,v) => storage[k]=v,
    showToast() {}, navigateTo: options => navigation.push(options.url), redirectTo: options => navigation.push(options.url),
    getWindowInfo: () => ({ windowWidth: 375, windowHeight: 680 }) };
  const state = { storageKey: () => `checkin_records_${storage.profile.id}`, dayKey: () => '2026-09-14' };
  vm.runInNewContext(fs.readFileSync(path.join(root,file),'utf8'), {
    Page: d => definition=d, Component: d => definition=d, wx, console,
    require: name => name.includes('qwen_chat') ? ai : name.includes('checkin-state') ? state : name.endsWith('qwen.js') ? ai : {},
  });
  const instance = { ...(component ? definition.methods : definition), data: JSON.parse(JSON.stringify(definition.data)) };
  instance.setData = patch => Object.assign(instance.data,patch);
  if(component) definition.lifetimes.attached.call(instance);
  if(!component && file.includes('consult-ai')) instance.onLoad();
  return { instance, storage, definition, navigation };
}
test('手动刷新绕过当天缓存，连续点击只生成一次；失败保留原建议', async () => {
  let calls = 0, resolve;
  const { instance:p, storage } = harness('pages/checkin/checkin.js', {
    generateDailySuggestions: () => { calls++; return new Promise(r => resolve=r); },
  });
  const key = 'ai_suggestions_checkin_records_7_2026-09-14';
  storage[key] = '缓存建议';
  p.loadAISuggestions(); assert.equal(calls,0); assert.equal(p.data.aiSuggestionText,'缓存建议');
  const request = p.refreshAISuggestions(); p.refreshAISuggestions();
  assert.equal(calls,1); assert.equal(p.data.loadingAI,true);
  resolve('新建议'); await request;
  assert.equal(storage[key],'新建议'); assert.equal(p.data.loadingAI,false);
  const failed = harness('pages/checkin/checkin.js', { generateDailySuggestions: async () => { throw new Error('offline'); } }).instance;
  failed.data.aiSuggestionText = '已有建议'; await failed.refreshAISuggestions();
  assert.equal(failed.data.aiSuggestionText,'已有建议'); assert.ok(failed.data.aiSuggestionError); assert.equal(failed.data.loadingAI,false);
});
test('悬浮球拖动吸边不误触，轻点进入 AI 二级页面且只导航一次', () => {
  const {instance:p,storage,navigation} = harness('components/ai-float/ai-float.js',{},true);
  assert.equal(p.data.x,271);
  p.touchStart({touches:[{clientX:300,clientY:500}]});
  p.touchMove({touches:[{clientX:-500,clientY:2000}]}); p.touchEnd(); p.openAiPage();
  assert.equal(p.data.x,16); assert.equal(p.data.y,478); assert.equal(navigation.length,0);
  assert.equal(storage.floating_ai_position.side,'left');
  p._ignoreTapUntil=0; p.touchStart({touches:[{clientX:20,clientY:200}]}); p.touchEnd(); p.openAiPage();
  assert.deepEqual(navigation,['/pages/consult-ai/consult-ai']);
});
test('预约内容自然撑开页面，悬浮球尺寸与屏幕定位一致', () => {
  const consult=fs.readFileSync(path.join(root,'pages/consult/consult.wxml'),'utf8');
  const consultStyle=fs.readFileSync(path.join(root,'pages/consult/consult.wxss'),'utf8');
  const orbStyle=fs.readFileSync(path.join(root,'components/ai-float/ai-float.wxss'),'utf8');
  assert.match(consult,/assignmentId \? 'chat-mode' : 'booking-mode'/);
  assert.match(consultStyle,/\.container\.booking-mode\s*\{[^}]*display:\s*block;[^}]*height:\s*auto;/);
  assert.match(orbStyle,/\.ai-orb\s*\{[^}]*box-sizing:\s*border-box;[^}]*width:\s*88px;/);
});
test('AI 二级页快捷问题正确携带文本与历史，成功保存回复并计次', async () => {
  let resolve, args, calls=0;
  const {instance:p,storage} = harness('pages/consult-ai/consult-ai.js',{chatWithHistory:(...a)=>{
    calls++; args=a; return new Promise(r=>resolve=r);
  }});
  p.clickTemplate({currentTarget:{dataset:{id:'diet'}}});
  assert.equal(calls,1); assert.match(args[0],/一日三餐/); assert.equal(args[1].length,0);
  p.sendMessage(); assert.equal(calls,1);
  resolve({reply:'搭配谷物、蛋白质和蔬果。'});
  await new Promise(setImmediate);
  assert.equal(p.data.sending,false); assert.equal(p.data.messages[1].role,'assistant');
  assert.equal(storage.floating_ai_7.length,2); assert.equal(storage.floating_ai_7_quota_2026_09_14,undefined);
  assert.equal(storage['floating_ai_7_quota_2026-09-14'],1);
});
test('AI 问答失败可重试且不计次，账号切换隔离会话', async () => {
  const {instance:p,storage} = harness('pages/consult-ai/consult-ai.js',{chatWithHistory:async()=>{throw new Error('offline');}});
  p.data.userInput='问题'; await p.sendMessage();
  assert.equal(p.data.userInput,'问题'); assert.equal(p.data.messages.length,0); assert.ok(p.data.error);
  assert.equal(storage['floating_ai_7_quota_2026-09-14'],undefined);
  let resolve;
  const other=harness('pages/consult-ai/consult-ai.js',{chatWithHistory:()=>new Promise(r=>resolve=r)});
  other.instance.data.userInput='旧账号问题'; const request=other.instance.sendMessage();
  other.storage.profile={id:8}; other.storage.token='session-8'; other.instance.restore();
  resolve({reply:'旧账号回复'}); await request;
  assert.equal(other.instance.data.messages.length,0); assert.equal(other.storage.floating_ai_8,undefined);
});
test('五个患者主页面均注册悬浮球，移除固定入口和两处表情图标', () => {
  for (const name of ['survey','checkin','consult','science','mine']) {
    const config=JSON.parse(fs.readFileSync(path.join(root,`pages/${name}/${name}.json`),'utf8'));
    assert.equal(config.usingComponents['ai-float'],'/components/ai-float/ai-float');
    const markup=fs.readFileSync(path.join(root,`pages/${name}/${name}.wxml`),'utf8');
    assert.equal((markup.match(/<ai-float\s*\/>/g)||[]).length,1);
    assert.doesNotMatch(markup,/ai-shortcut|ai-ask-banner/);
    if(name==='checkin') { assert.doesNotMatch(markup,/🤖|🔄/); assert.match(markup,/bindtap="refreshAISuggestions"/); }
  }
});
