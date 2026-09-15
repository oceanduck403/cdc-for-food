const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.join(__dirname, '..');

function adminPage(changeAccount) {
  let definition;
  const calls = [];
  const toasts = [];
  const auth = { logout: url => calls.push(['logout', url]) };
  const wx = {
    showToast: options => toasts.push(options.title),
    showLoading() {}, hideLoading() {},
    showModal: options => options.complete({ confirm: true }),
  };
  const sandbox = {
    Page: value => { definition = value; },
    wx, console,
    require: name => name.includes('auth.js') ? auth
      : name.includes('admin.js') ? { changeAccount } : {},
  };
  vm.runInNewContext(fs.readFileSync(path.join(root, 'pages/admin/admin.js'), 'utf8'), sandbox);
  const page = { ...definition, data: JSON.parse(JSON.stringify(definition.data)) };
  page.data.profile = { username: 'old_admin' };
  page.setData = changes => {
    for (const [key, value] of Object.entries(changes)) {
      if (key.startsWith('accountForm.')) page.data.accountForm[key.slice(12)] = value;
      else page.data[key] = value;
    }
  };
  return { page, calls, toasts };
}

test('管理员可单独修改账号并重新登录', async () => {
  const requests = [];
  const { page, calls } = adminPage(async (...args) => requests.push(args));
  page.openChangeAccount();
  assert.equal(page.data.accountForm.username, 'old_admin');
  page.onAccountFieldInput({ currentTarget: { dataset: { field: 'username' } }, detail: { value: 'new_admin' } });
  page.onAccountFieldInput({ currentTarget: { dataset: { field: 'current' } }, detail: { value: 'Original-123' } });
  await page.submitChangeAccount();
  assert.equal(JSON.stringify(requests), JSON.stringify([['Original-123', 'new_admin', '']]));
  assert.equal(page.data.showChangeAccount, false);
  assert.equal(page.data.accountForm.current, '');
  assert.equal(JSON.stringify(calls), JSON.stringify([['logout', '/pages/admin-login/admin-login']]));
});

test('修改密码需确认一致，后端拒绝时保留表单以便更正', async () => {
  let requests = 0;
  const { page, calls, toasts } = adminPage(async () => { requests++; throw Error('原密码错误'); });
  page.openChangeAccount();
  Object.assign(page.data.accountForm, { current: 'wrong', next: 'New-password-456', confirm: 'different' });
  await page.submitChangeAccount();
  assert.equal(requests, 0);
  assert.ok(toasts.includes('两次新密码不一致'));
  page.data.accountForm.confirm = 'New-password-456';
  await page.submitChangeAccount();
  assert.equal(requests, 1);
  assert.ok(toasts.includes('原密码错误'));
  assert.equal(page.data.showChangeAccount, true);
  assert.equal(calls.length, 0);
});

test('退出到管理员登录页时清除旧账号的本地会话', () => {
  const storage = { token: 'old-token', role: 'admin', profile: { username: 'old_admin' }, userInfo: { username: 'old_admin' } };
  const app = { globalData: { ...storage } };
  const routes = [];
  const sandbox = {
    module: { exports: {} }, require: () => ({}), getApp: () => app,
    wx: { removeStorageSync: key => delete storage[key], reLaunch: options => routes.push(options.url) },
  };
  vm.runInNewContext(fs.readFileSync(path.join(root, 'utils/auth.js'), 'utf8'), sandbox);
  sandbox.module.exports.logout('/pages/admin-login/admin-login');
  assert.equal(storage.token, undefined);
  assert.equal(storage.role, undefined);
  assert.equal(storage.profile, undefined);
  assert.equal(storage.userInfo, undefined);
  assert.equal(app.globalData.token, '');
  assert.equal(JSON.stringify(routes), JSON.stringify(['/pages/admin-login/admin-login']));
});
