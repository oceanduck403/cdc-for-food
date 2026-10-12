const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function harness() {
  const requests = [];
  const storage = { token: 'test-session' };
  const app = { globalData: {} };
  let response = { statusCode: 200, data: { reply: '科普回复', items: [] } };
  const wx = {
    getStorageSync: key => storage[key],
    removeStorageSync: key => { delete storage[key]; },
    showLoading() {}, hideLoading() {}, showToast() {},
    request: options => { requests.push(options); options.success(response); },
  };
  const modules = {
    './config.js': {
      useMock: false,
      getApiRuntime: () => ({ mode: 'direct', apiBase: 'https://example.test/api/v1', cloud: {} }),
    },
    './mock.js': {},
  };
  function load(name) {
    if (modules[name]) return modules[name];
    const module = { exports: {} };
    vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../utils', name), 'utf8'), {
      module, require: load, wx, getApp: () => app, console,
    });
    modules[name] = module.exports;
    return module.exports;
  }
  return { load, requests, storage, respond: value => { response = value; } };
}

test('两种请求包装都保留普通请求10秒超时，允许单次请求延长等待', async () => {
  for (const name of ['./api.js', './request.js']) {
    const h = harness();
    const { request } = h.load(name);
    await request({ url: '/survey/templates' });
    await request({ url: '/ai/chat', method: 'POST', timeout: 45000 });
    assert.equal(h.requests[0].timeout, 10000);
    assert.equal(h.requests[1].timeout, 45000);
    assert.equal(h.requests[1].header.Authorization, 'Bearer test-session');
  }
});

test('所有文字、问卷、每日建议和识图AI入口均实际发送45秒超时', async () => {
  const h = harness();
  const ai = h.load('./qwen_chat.js');
  await ai.chat('早餐怎样搭配');
  await ai.chatWithHistory('食品标签怎么看', []);
  await ai.analyzeSurvey('health', { diet: '规律' });
  await ai.generateDailySuggestions({ water: true }, {});
  await h.load('./qwen.js').callQwenVL('test-image-base64');
  assert.deepEqual(h.requests.map(item => item.url), [
    '/ai/chat', '/ai/chat', '/ai/survey-analysis', '/ai/daily-suggestion', '/ai/food-analysis',
  ].map(url => `https://example.test/api/v1${url}`));
  assert.ok(h.requests.every(item => item.timeout === 45000));
});

test('API包装保留统一业务错误的可读消息、错误码与HTTP状态', async () => {
  const h = harness();
  h.respond({ statusCode: 502, data: { code: 'AI_UPSTREAM_ERROR', message: 'AI 服务暂时不可用，请稍后重试', data: null } });
  await assert.rejects(h.load('./api.js').request('/ai/chat'), error => {
    assert.equal(error.message, 'AI 服务暂时不可用，请稍后重试');
    assert.equal(error.code, 'AI_UPSTREAM_ERROR');
    assert.equal(error.statusCode, 502);
    return true;
  });
});

test('API包装兼容detail旧格式，校验数组不会变成用户看不懂的对象文本', async () => {
  const h = harness();
  const { request } = h.load('./api.js');
  h.respond({ statusCode: 404, data: { detail: '问卷不存在或已停用' } });
  await assert.rejects(request('/survey/templates/1'), { message: '问卷不存在或已停用', code: 'HTTP_ERROR' });
  h.respond({ statusCode: 422, data: { detail: [{ msg: 'field required' }] } });
  await assert.rejects(request('/survey/responses'), { message: '请求失败 422' });
});

test('AI实际使用的请求包装保留后端统一业务错误消息和错误码', async () => {
  const h = harness();
  h.respond({ statusCode: 429, data: { code: 'AI_DAILY_LIMIT', message: '今日 AI 使用次数已用完，请明天再试' } });
  await assert.rejects(h.load('./qwen_chat.js').chat('早餐怎样搭配'), error => {
    assert.equal(error.message, '今日 AI 使用次数已用完，请明天再试');
    assert.equal(error.code, 'AI_DAILY_LIMIT');
    return true;
  });
});
