// node --test miniprogram/tests/survey.test.js；只模拟微信 API，不发送网络请求。
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { normalizeQuestions, currentQuestions } = require('../utils/survey-form');

function loadPage(name, api = {}, storage = {}) {
  let definition;
  const navigation = [];
  const wx = {
    getStorageSync: key => storage[key],
    setStorageSync: (key, value) => { storage[key] = value; },
    removeStorageSync: key => { delete storage[key]; },
    showLoading() {}, hideLoading() {}, showToast() {}, showModal() {},
    navigateTo: args => navigation.push(args.url), navigateBack() {}, pageScrollTo() {},
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, `../pages/${name}/${name}.js`), 'utf8'), {
    Page: value => { definition = value; }, wx, console, setTimeout: () => {},
    require: name => name.endsWith('/navigation.js') ? { open: wx.navigateTo } : name.endsWith('/survey.js') ? api : name.endsWith('/survey-form.js') ? { normalizeQuestions, currentQuestions } : {},
  });
  const page = { ...definition, data: JSON.parse(JSON.stringify(definition.data)) };
  page.setData = patch => {
    for (const [key, value] of Object.entries(patch)) {
      const parts = key.split('.');
      let obj = page.data;
      while (parts.length > 1) { const part = parts.shift(); obj = obj[part] || (obj[part] = {}); }
      obj[parts[0]] = value;
    }
  };
  return { page, navigation, storage };
}

test('返回缓存的调查页时重新加载问卷，从空列表恢复到新开放的问卷', async () => {
  let templates = [];
  const { page } = loadPage('survey', {
    getTemplates: async () => templates,
    getMyResponses: async () => [],
  });
  await page.onShow();
  assert.equal(page.data.surveyTypes.length, 0);
  templates = [{ id: 5, type: 'weight_visit_registration', name: '就诊登记', questions: [] }];
  await page.onShow();
  assert.equal(page.data.surveyTypes.length, 1);
  assert.equal(page.data.loadError, '');
  assert.equal(page.data.loading, false);
});

test('无效问卷响应显示错误而非暂无问卷，重试成功后清除错误', async () => {
  let response = null;
  const { page } = loadPage('survey', { getTemplates: async () => response });
  await page.loadTemplates();
  assert.match(page.data.loadError, /数据加载异常/);
  response = [{ id: 5, type: 'weight_visit_registration', name: '就诊登记', questions: [] }];
  await page.loadTemplates();
  assert.equal(page.data.surveyTypes.length, 1);
  assert.equal(page.data.loadError, '');
});

test('重复刷新不会并发加载模板，历史请求失败也不清空问卷', async () => {
  let resolve, calls = 0;
  const { page } = loadPage('survey', {
    getTemplates: () => { calls++; return new Promise(r => { resolve = r; }); },
    getMyResponses: async () => { throw new Error('未登录'); },
  });
  const first = page.onShow();
  const second = page.onShow();
  assert.equal(calls, 1);
  resolve([{ id: 5, type: 'weight_visit_registration', name: '就诊登记', questions: [] }]);
  await Promise.all([first, second]);
  assert.equal(page.data.surveyTypes.length, 1);
  assert.equal(page.data.loadError, '');
});

test('点击卡片从列表对象取得 ID，不依赖缺失的 dataset.templateid', () => {
  const { page, navigation } = loadPage('survey');
  page.data.surveyTypes = [{ id: 'remote_5', type: 'remote', templateId: 5, templateType: 'weight_visit_registration', title: '登记表' }];
  page.startSurvey({ currentTarget: { dataset: { type: 'remote_5' } } });
  assert.match(navigation[0], /templateId=5&/);
  page.data.surveyTypes[0].templateId = undefined;
  page.startSurvey({ currentTarget: { dataset: { type: 'remote_5' } } });
  assert.equal(navigation.length, 1);
});

test('JSON 题目、缺失步骤和非连续步骤均生成有效页面及多选状态', () => {
  const qs = normalizeQuestions(JSON.stringify([
    { id: 'a', title: '姓名', type: 'input' },
    { id: 'b', title: '选择', type: 'checkbox', step: '3', options: ['是', '否'] },
  ]));
  assert.deepEqual(qs.map(q => q.step), [0, 1]);
  assert.equal(currentQuestions(qs, 0, {}).length, 1);
  assert.equal(currentQuestions(qs, 1, { b: ['否'] })[0].choices[1].selected, true);
});

test('原生导航卡片包含模板 ID 和编码后的标题', async () => {
  const { page } = loadPage('survey', { getTemplates: async () => [{ id: 5, type: 'weight_visit_registration', name: '登记 & 回访', questions: [] }] });
  await page.loadTemplates();
  const url = new URL(page.data.surveyTypes[0].url, 'https://test.invalid');
  assert.equal(url.searchParams.get('templateId'), '5');
  assert.equal(url.searchParams.get('title'), '登记 & 回访');
  assert.equal(url.pathname, '/pages/survey-form/survey-form');
});

test('接口地址统一使用配置，切换服务器无需修改请求封装', async () => {
  const calls = [], config = { apiBase: 'http://192.168.0.102:8000/api/v1' };
  const transport = { getDirectBaseUrl: () => config.apiBase.replace(/\/api\/v1$/, ''), send: options => {
    calls.push({ ...options, url: config.apiBase + options.url });
    options.success({ statusCode: 200, data: {} });
  } };
  const sandbox = { module: { exports: {} }, require: name => name.includes('transport') ? transport : name.includes('config') ? config : { networkError: e => e }, wx: {
    getStorageSync: () => '',
  } };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../utils/api.js'), 'utf8'), sandbox);
  await sandbox.module.exports.request('/survey/templates');
  assert.equal(calls[0].url, config.apiBase + '/survey/templates');
  config.apiBase = 'https://example.invalid/api/v1';
  await sandbox.module.exports.request('/survey/templates');
  assert.equal(calls[1].url, config.apiBase + '/survey/templates');
});

test('应用恢复时无登录不请求，次数接口失败不抛出生命周期异常', async () => {
  let token = '', calls = 0;
  const sandbox = { module: { exports: {} }, console: { warn() {} }, wx: { getStorageSync: () => token },
    require: name => name.includes('config') ? {} : { request: async () => { calls++; throw new Error('断网'); } },
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../utils/auth.js'), 'utf8'), sandbox);
  const app = { globalData: { dailyAnalysisCount: 0 } };
  await sandbox.module.exports.refreshDailyQuota(app);
  assert.equal(calls, 0);
  token = 'test-token';
  await sandbox.module.exports.refreshDailyQuota(app);
  assert.equal(calls, 1);
  assert.equal(app.globalData.dailyAnalysisCount, 0);
});

test('详情加载、翻页保留答案、提交成功禁止重复提交', async () => {
  let requests = 0;
  const questions = [
    { id: 'name', title: '姓名', type: 'input', step: 0 },
    { id: 'phone', title: '联系电话', type: 'input', step: 0 },
    { id: 'follow_up_date', title: '复诊日期', type: 'date', step: 1 },
  ];
  const { page } = loadPage('survey-form', {
    getTemplate: async id => { assert.equal(id, 5); return { type: 'weight_visit_registration', name: '登记表', questions }; },
    submitResponse: async payload => { requests++; assert.equal(payload.user_name, '测试姓名'); assert.equal(payload.user_phone, '028-00000000'); return { id: 9 }; },
  });
  await page.onLoad({ templateId: '5' });
  assert.equal(page.data.currentQuestions.length, 2);
  page.onInputChange({ currentTarget: { dataset: { id: 'name' } }, detail: { value: '测试姓名' } });
  page.onInputChange({ currentTarget: { dataset: { id: 'phone' } }, detail: { value: '028-00000000' } });
  page.nextStep();
  assert.equal(page.data.currentQuestions[0].id, 'follow_up_date');
  page.onInputChange({ currentTarget: { dataset: { id: 'follow_up_date' } }, detail: { value: '2026-10-12' } });
  page.clearDate({ currentTarget: { dataset: { id: 'follow_up_date' } } });
  assert.equal(page.data.answers.follow_up_date, '');
  page.prevStep();
  assert.equal(page.data.answers.name, '测试姓名');
  await page.doSubmit();
  await page.doSubmit();
  assert.equal(requests, 1);
  assert.equal(page.data.mode, 'view');
});

test('无效链接、空模板及网络失败显示错误，支持重试，不能提交空表', async () => {
  let fail = true, requests = 0;
  const { page } = loadPage('survey-form', {
    getTemplate: async () => { requests++; if (fail) throw new Error('网络错误'); return { questions: [{ id: 'q', title: '姓名' }] }; },
  });
  await page.onLoad({ templateId: 'undefined' });
  assert.equal(requests, 0);
  assert.ok(page.data.loadError);
  await page.loadRemoteTemplate(5);
  assert.equal(page.data.loadError, '网络错误');
  fail = false;
  await page.retryLoad();
  assert.equal(page.data.loadError, '');
  assert.equal(page.data.currentQuestions.length, 1);
  const empty = loadPage('survey-form', { getTemplate: async () => ({ questions: [] }) }).page;
  await empty.loadRemoteTemplate(5);
  assert.equal(empty.data.totalSteps, 0);
  assert.ok(empty.data.loadError);
  await empty.doSubmit();
  assert.equal(empty.data.submitted, false);
});

test('历史记录可跨页查看，单选和输入不可修改，本地记录可读', async () => {
  const questions = [{ id: 'a', title: '性别', type: 'radio', options: ['男', '女'], step: 0 }, { id: 'b', title: '备注', type: 'input', step: 1 }];
  const { page } = loadPage('survey-form', { getMyResponseDetail: async () => ({ template_type: 'test', questions, answers: { a: '女' } }) });
  await page.onLoad({ id: '1' });
  page.onRadioChange({ currentTarget: { dataset: { id: 'a', value: '男' } } });
  assert.equal(page.data.answers.a, '女');
  page.nextStep();
  assert.equal(page.data.currentQuestions[0].id, 'b');
  const local = loadPage('survey-form', {}, { survey_history: [{ id: 100, type: 'test', questions, answers: { a: '男' } }] }).page;
  await local.onLoad({ id: '100' });
  assert.equal(local.data.answers.a, '男');
  assert.equal(local.data.loadError, '');
});

test('问卷提交与管理操作使用正确的 HTTP 方法和参数', async () => {
  const calls = [];
  const sandbox = { module: { exports: {} }, require: () => ({ request: options => { calls.push(options); return Promise.resolve({}); } }) };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../utils/survey.js'), 'utf8'), sandbox);
  const api = sandbox.module.exports;
  await api.submitResponse({ template_id: 5 });
  await api.adminCreateTemplate({ name: '测试' });
  await api.adminUpdateTemplate(5, { name: '新名' });
  await api.adminDeleteTemplate(5);
  await api.adminListResponses({ keyword: '登记' });
  assert.deepEqual(calls.slice(0, 4).map(c => c.method), ['POST', 'POST', 'PUT', 'DELETE']);
  assert.equal(calls[0].url, '/survey/responses');
  assert.equal(calls[0].data.template_id, 5);
  assert.equal(calls[4].data.keyword, '登记');
});

test('问卷草稿按账号隔离，题目变更时不恢复旧答案', async () => {
  const storage = { profile: { id: 15 } };
  const api = { getTemplate: async () => ({ questions: [{ id: 'name', title: '姓名', type: 'input' }] }) };
  const first = loadPage('survey-form', api, storage).page;
  await first.onLoad({ templateId: '5' });
  first.onInputChange({ currentTarget: { dataset: { id: 'name' } }, detail: { value: '草稿姓名' } });
  const reopened = loadPage('survey-form', api, storage).page;
  await reopened.onLoad({ templateId: '5' });
  assert.equal(reopened.data.answers.name, '草稿姓名');
  storage.profile.id = 16;
  const other = loadPage('survey-form', api, storage).page;
  await other.onLoad({ templateId: '5' });
  assert.equal(other.data.answers.name, undefined);
  storage.profile.id = 15;
  const changed = loadPage('survey-form', { getTemplate: async () => ({ questions: [{ id: 'name', title: '新题目' }] }) }, storage).page;
  await changed.onLoad({ templateId: '5' });
  assert.equal(changed.data.answers.name, undefined);
});
