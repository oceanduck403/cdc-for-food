const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../utils/transport.js'), 'utf8');

function loadTransport(runtime, wx) {
  const sandbox = {
    module: { exports: {} },
    require: () => ({ getApiRuntime: () => runtime }),
    wx,
    Uint8Array,
    ArrayBuffer,
    Promise,
    Date,
    Math,
    encodeURIComponent,
    unescape,
  };
  vm.runInNewContext(source, sandbox);
  return sandbox.module.exports;
}

test('云托管请求只初始化一次，并统一附加环境、服务名和 API 前缀', async () => {
  const calls = [];
  let initCount = 0;
  const wx = { cloud: {
    init: options => { initCount += 1; calls.push({ init: options }); },
    callContainer: options => { calls.push(options); return Promise.resolve({ statusCode: 200, data: { ok: true } }); },
  } };
  const transport = loadTransport({
    mode: 'cloud',
    cloud: { envId: 'prod-env', service: 'api-service', apiPrefix: '/api/v1' },
  }, wx);
  const responses = [];
  await transport.send({ url: '/health', method: 'GET', header: { Authorization: 'Bearer t' }, success: r => responses.push(r) });
  await transport.send({ url: 'survey/templates', method: 'POST', data: { a: 1 } });
  assert.equal(initCount, 1);
  assert.equal(calls[1].config.env, 'prod-env');
  assert.equal(calls[1].path, '/api/v1/health');
  assert.equal(calls[1].header['X-WX-SERVICE'], 'api-service');
  assert.equal(calls[1].header.Authorization, 'Bearer t');
  assert.equal(calls[2].path, '/api/v1/survey/templates');
  assert.equal(responses[0].data.ok, true);
});

test('开发直连使用运行时地址，外部绝对地址不拼接 API 前缀', () => {
  const calls = [];
  const wx = { request: options => { calls.push(options); return { abort() {} }; } };
  const transport = loadTransport({ mode: 'direct', apiBase: 'http://10.0.0.8:8000/api/v1', cloud: {} }, wx);
  transport.send({ url: '/users/me' });
  transport.send({ url: 'https://example.test/data.json' });
  assert.equal(calls[0].url, 'http://10.0.0.8:8000/api/v1/users/me');
  assert.equal(calls[1].url, 'https://example.test/data.json');
});

test('云托管图片上传生成 multipart 请求并保持 wx.uploadFile 回调格式', async () => {
  let containerOptions;
  const file = Uint8Array.from([1, 2, 3]).buffer;
  const wx = {
    getFileSystemManager: () => ({ readFile: options => options.success({ data: file }) }),
    cloud: {
      init() {},
      callContainer: options => {
        containerOptions = options;
        return Promise.resolve({ statusCode: 200, data: { avatar: '/media/a.jpg' } });
      },
    },
  };
  const transport = loadTransport({
    mode: 'cloud',
    cloud: { envId: 'prod-env', service: 'api-service', apiPrefix: '/api/v1' },
  }, wx);
  const result = await new Promise((resolve, reject) => transport.uploadFile({
    url: '/users/me/avatar', filePath: 'wxfile://photo.jpg', name: 'file',
    header: { Authorization: 'Bearer t' }, success: resolve, fail: reject,
  }));
  assert.equal(containerOptions.path, '/api/v1/users/me/avatar');
  assert.match(containerOptions.header['content-type'], /^multipart\/form-data; boundary=/);
  assert.equal(containerOptions.header['X-WX-SERVICE'], 'api-service');
  assert.ok(containerOptions.data instanceof ArrayBuffer);
  assert.equal(JSON.parse(result.data).avatar, '/media/a.jpg');
});

test('云托管相对图片经私有链路下载到本地缓存，重复渲染不重复请求', async () => {
  let containerCalls = 0;
  let saved;
  const bytes = Uint8Array.from([4, 5, 6]).buffer;
  const wx = {
    env: { USER_DATA_PATH: 'wxfile://user' },
    getFileSystemManager: () => ({
      writeFile: options => { saved = options; options.success(); },
    }),
    cloud: {
      init() {},
      callContainer: options => {
        containerCalls += 1;
        assert.equal(options.responseType, 'arraybuffer');
        return Promise.resolve({ statusCode: 200, data: bytes });
      },
    },
  };
  const transport = loadTransport({
    mode: 'cloud',
    cloud: { envId: 'prod-env', service: 'api-service', apiPrefix: '/api/v1' },
  }, wx);
  const url = '/api/v1/media/avatar/a.jpg?expires=1&sig=test';
  const [first, second] = await Promise.all([transport.resolveMediaUrl(url), transport.resolveMediaUrl(url)]);
  assert.equal(first, second);
  assert.match(first, /^wxfile:\/\/user\/cdc-media-/);
  assert.equal(saved.data, bytes);
  assert.equal(containerCalls, 1);
});
