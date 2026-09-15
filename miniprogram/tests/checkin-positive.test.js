const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.join(__dirname, '..');

test('打卡后即时更新今日与七日足迹，重复点击不会重复计数', () => {
  const storage = { profile: { id: 17 } };
  const toasts = [];
  const wx = {
    getStorageSync: key => storage[key],
    setStorageSync: (key, value) => { storage[key] = value; },
    showToast: options => toasts.push(options.title),
    vibrateShort() {},
  };
  const helperSandbox = { module: { exports: {} }, wx, Date, Set };
  vm.runInNewContext(fs.readFileSync(path.join(root, 'utils/checkin-state.js'), 'utf8'), helperSandbox);
  const checkinState = helperSandbox.module.exports;
  let definition;
  const pageSandbox = {
    Page: page => { definition = page; }, wx, console, Date,
    require: name => name.includes('checkin-state.js') ? checkinState
      : name.includes('qwen_chat.js') ? { generateDailySuggestions: async () => '' }
      : name.includes('navigation.js') ? { open() {} } : {},
  };
  vm.runInNewContext(fs.readFileSync(path.join(root, 'pages/checkin/checkin.js'), 'utf8'), pageSandbox);
  const page = { ...definition, data: JSON.parse(JSON.stringify(definition.data)) };
  page.setData = changes => Object.assign(page.data, changes);
  page.loadTodayData();
  assert.equal(page.data.positiveFeedback.doneCount, 0);
  for (const type of ['diet', 'diet', 'exercise', 'water']) {
    page.doCheckin({ currentTarget: { dataset: { type } } });
  }
  assert.equal(storage[checkinState.storageKey()].length, 3);
  assert.equal(page.data.positiveFeedback.doneCount, 3);
  assert.equal(page.data.positiveFeedback.percent, 100);
  assert.equal(page.data.positiveFeedback.weekDays, 1);
  assert.equal(page.data.positiveFeedback.weekTrail.at(-1).active, true);
  assert.equal(toasts.at(-1), '今日三项完成');

  const markup = fs.readFileSync(path.join(root, 'pages/checkin/checkin.wxml'), 'utf8');
  assert.doesNotMatch(markup, /免费预约医生|加入群组|指导群组|医生在线指导/);
});
