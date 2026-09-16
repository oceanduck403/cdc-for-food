const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../pages/mine/mine.js'), 'utf8');

function harness() {
  let definition;
  const requests = [];
  const modals = [];
  const toasts = [];
  const removed = [];
  let logoutCount = 0;
  let shouldFail = false;
  const memory = {
    token: 'patient-token', role: 'patient',
    profile: { id: 27, nickname: '用户', role: 'patient' },
    userInfo: { id: 27 }, history: ['private'], survey_history: ['private'],
    checkin_records_27: ['private'], floating_ai_27: ['private'],
    floating_ai_27_quota_20260915: 2, survey_draft_27_1: { private: true },
    ai_suggestions_checkin_records_27_2026_09_15: 'private',
    checkin_records_99: ['other'], privacy_accepted: 'keep',
  };
  const storage = { get: key => memory[key] };
  const wx = {
    showModal: options => modals.push(options),
    showLoading() {}, hideLoading() {},
    showToast: options => toasts.push(options.title),
    getStorageInfoSync: () => ({ keys: Object.keys(memory) }),
    removeStorageSync: key => { removed.push(key); delete memory[key]; },
    makePhoneCall() {},
  };
  const request = options => {
    requests.push(options);
    return shouldFail ? Promise.reject(new Error('网络异常')) : Promise.resolve({ deleted: true });
  };
  const sandbox = {
    Page: value => { definition = value; },
    wx, console,
    getApp: () => ({ globalData: {} }),
    setTimeout: callback => callback(),
    require: name => name.includes('storage.js') ? storage
      : name.includes('config.js') ? { baseUrl: 'https://api.example.test' }
      : name.includes('navigation.js') ? { open() {}, login() {} }
      : name.includes('auth.js') ? { logout: () => { logoutCount += 1; } }
      : name.includes('api.js') ? { request }
      : {},
  };
  vm.runInNewContext(source, sandbox);
  const page = { ...definition, data: { ...definition.data } };
  page.setData = changes => Object.assign(page.data, changes);
  page.onShow();
  return {
    page, memory, requests, modals, removed, toasts,
    logoutCount: () => logoutCount,
    failRequest: () => { shouldFail = true; },
  };
}

async function settle() {
  await Promise.resolve();
  await new Promise(setImmediate);
}

test('账号注销经过两次明确确认并清理当前用户本地数据', async () => {
  const state = harness();
  const deletion = state.page.onDeleteAccount();
  assert.equal(state.modals.length, 1);
  assert.match(state.modals[0].content, /永久删除/);
  state.modals[0].success({ confirm: true });
  await settle();
  assert.equal(state.modals.length, 2);
  assert.match(state.modals[1].title, /最后确认/);
  state.modals[1].success({ confirm: true });
  await deletion;

  assert.equal(state.requests.length, 1);
  assert.equal(state.requests[0].url, '/users/me');
  assert.equal(state.requests[0].method, 'DELETE');
  assert.equal(state.requests[0].data.confirmation, '注销账号');
  for (const key of [
    'token', 'role', 'profile', 'userInfo', 'history', 'survey_history',
    'checkin_records_27', 'floating_ai_27', 'floating_ai_27_quota_20260915',
    'survey_draft_27_1', 'ai_suggestions_checkin_records_27_2026_09_15',
  ]) assert.equal(state.memory[key], undefined, key);
  assert.deepEqual(state.memory.checkin_records_99, ['other']);
  assert.equal(state.memory.privacy_accepted, 'keep');
  assert.equal(state.logoutCount(), 1);
  assert.ok(state.toasts.includes('账号已注销'));
});

test('任一步取消或服务端失败都不清理本地会话', async () => {
  const firstCancel = harness();
  const cancelled = firstCancel.page.onDeleteAccount();
  firstCancel.modals[0].success({ confirm: false });
  await cancelled;
  assert.equal(firstCancel.requests.length, 0);
  assert.equal(firstCancel.memory.token, 'patient-token');

  const secondCancel = harness();
  const cancelledLate = secondCancel.page.onDeleteAccount();
  secondCancel.modals[0].success({ confirm: true });
  await settle();
  secondCancel.modals[1].success({ confirm: false });
  await cancelledLate;
  assert.equal(secondCancel.requests.length, 0);
  assert.equal(secondCancel.memory.token, 'patient-token');

  const failed = harness();
  failed.failRequest();
  const attempt = failed.page.onDeleteAccount();
  failed.modals[0].success({ confirm: true });
  await settle();
  failed.modals[1].success({ confirm: true });
  await attempt;
  assert.equal(failed.memory.token, 'patient-token');
  assert.equal(failed.logoutCount(), 0);
  assert.ok(failed.toasts.includes('网络异常'));
});

test('我的页为已登录患者展示可理解的注销入口', () => {
  const markup = fs.readFileSync(path.join(__dirname, '../pages/mine/mine.wxml'), 'utf8');
  assert.match(markup, /wx:if="\{\{isLogin\}\}" bindtap="onDeleteAccount"/);
  assert.match(markup, /永久删除账号及个人数据/);
});
