const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../pages/profile/profile.js'), 'utf8');

function harness() {
  let definition;
  let pageCount = 0;
  let chooseMediaOptions;
  let actionSheetOptions;
  let uploadOptions;
  let compressOptions;
  const requests = [];
  const toasts = [];
  const saved = { id: 7, nickname: '原昵称', avatar: '/uploads/avatars/7-old.jpg', role: 'patient' };
  const memory = { token: 'valid-token', profile: { ...saved } };
  const app = { globalData: {} };
  const storage = {
    get: key => memory[key],
    set: (key, value) => { memory[key] = value; },
  };
  const wx = {
    showToast: options => toasts.push(options.title),
    showLoading() {}, hideLoading() {},
    showActionSheet: options => { actionSheetOptions = options; },
    chooseMedia: options => { chooseMediaOptions = options; },
    compressImage: options => { compressOptions = options; },
    uploadFile: options => { uploadOptions = options; },
  };
  const request = options => {
    requests.push(options);
    if (options.method === 'PUT') Object.assign(saved, options.data);
    return Promise.resolve({ ...saved });
  };
  const sandbox = {
    Page: value => { definition = value; pageCount++; },
    wx, getApp: () => app, console,
    require: name => name.includes('request.js') ? { request }
      : name.includes('storage.js') ? storage
      : name.includes('config.js') ? { apiBase: 'https://api.example.test/api/v1', baseUrl: 'https://api.example.test' }
      : name.includes('nutrition.js') ? { bmrMifflin: () => 1000, tdee: () => 1200 }
      : {},
  };
  vm.runInNewContext(source, sandbox);
  const page = { ...definition, data: { ...definition.data } };
  page.setData = (changes, callback) => {
    for (const [key, value] of Object.entries(changes)) {
      const parts = key.split('.');
      if (parts.length === 1) page.data[key] = value;
      else page.data[parts[0]][parts[1]] = value;
    }
    if (callback) callback();
  };
  return { page, pageCount, memory, app, requests, toasts,
    actionSheet: () => actionSheetOptions,
    chooseMedia: () => chooseMediaOptions,
    upload: () => uploadOptions,
    compress: () => compressOptions,
  };
}

test('个人资料仅注册一个页面，昵称持久化并同步我的页缓存', async () => {
  const { page, pageCount, memory, app, requests } = harness();
  assert.equal(pageCount, 1);
  page.onShow();
  await new Promise(setImmediate);
  assert.equal(page.data.avatarDisplayUrl, 'https://api.example.test/uploads/avatars/7-old.jpg');
  page.onInput({ currentTarget: { dataset: { field: 'nickname' } }, detail: { value: '  新昵称  ' } });
  await page.saveNickname();
  assert.equal(requests.at(-1).data.nickname, '新昵称');
  assert.equal(memory.profile.nickname, '新昵称');
  assert.equal(memory.userInfo.nickname, '新昵称');
  assert.equal(app.globalData.profile.nickname, '新昵称');
});

test('头像可选相册和拍照，服务端返回路径用于刷新后显示', async () => {
  const state = harness();
  state.page.onShow();
  await new Promise(setImmediate);
  state.page.chooseAvatar();
  state.actionSheet().success({ tapIndex: 0 });
  assert.equal(state.chooseMedia().sourceType[0], 'album');
  state.chooseMedia().success({ tempFiles: [{ tempFilePath: 'wxfile://photo.jpg', size: 1024 }] });
  assert.match(state.upload().url, /\/users\/me\/avatar$/);
  assert.equal(state.upload().header.Authorization, 'Bearer valid-token');
  state.upload().success({ statusCode: 200, data: JSON.stringify({ id: 7, nickname: '原昵称', avatar: '/uploads/avatars/7-new.jpg' }) });
  state.upload().complete();
  assert.equal(state.memory.profile.avatar, '/uploads/avatars/7-new.jpg');
  assert.equal(state.page.data.avatarDisplayUrl, 'https://api.example.test/uploads/avatars/7-new.jpg');
  state.page.chooseAvatar();
  state.actionSheet().success({ tapIndex: 1 });
  assert.equal(state.chooseMedia().sourceType[0], 'camera');
});

test('大于 5 MB 的手机照片先压缩再上传', () => {
  const state = harness();
  state.page.pickAvatar('camera');
  state.chooseMedia().success({ tempFiles: [{ tempFilePath: 'wxfile://large.jpg', size: 6 * 1024 * 1024 }] });
  assert.equal(state.compress().src, 'wxfile://large.jpg');
  assert.equal(state.upload(), undefined);
  state.compress().success({ tempFilePath: 'wxfile://compressed.jpg' });
  assert.equal(state.upload().filePath, 'wxfile://compressed.jpg');
});
