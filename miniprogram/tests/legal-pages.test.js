const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.join(__dirname, '..');

function read(relative) {
  return fs.readFileSync(path.join(root, relative), 'utf8');
}

test('完整隐私政策和用户条款页面已注册，并可从登录页与我的页进入', () => {
  const app = JSON.parse(read('app.json'));
  assert.ok(app.pages.includes('pages/legal/legal'));

  const loginJs = read('pages/login/login.js');
  const mineJs = read('pages/mine/mine.js');
  assert.match(loginJs, /\/pages\/legal\/legal\?type=privacy/);
  assert.match(loginJs, /\/pages\/legal\/legal\?type=terms/);
  assert.match(mineJs, /\/pages\/legal\/legal\?type=privacy/);
  assert.match(mineJs, /\/pages\/legal\/legal\?type=terms/);

  const loginMarkup = read('pages/login/login.wxml');
  const mineMarkup = read('pages/mine/mine.wxml');
  assert.match(loginMarkup, /《隐私政策》/);
  assert.match(loginMarkup, /《用户服务条款》/);
  assert.match(mineMarkup, />隐私政策</);
  assert.match(mineMarkup, />用户服务条款</);
});

test('法律内容覆盖现有功能、敏感健康信息与注销，并删除过时承诺', () => {
  const source = read('utils/legal-content.js');
  const docs = [
    fs.readFileSync(path.join(root, '../docs/legal/privacy-policy.md'), 'utf8'),
    fs.readFileSync(path.join(root, '../docs/legal/user-terms.md'), 'utf8'),
  ].join('\n');
  const all = `${source}\n${docs}`;

  for (const phrase of [
    '健康评估', '健康打卡', '科普互动', '医生在线指导', 'AI 问答',
    '食物分析', '评论', '点赞', '收藏', '互动消息', '头像', '昵称', '注销账号',
    '成都市疾病预防控制中心提供', '不作为诊疗依据',
  ]) assert.match(all, new RegExp(phrase));

  for (const stale of [
    '毒蘑菇风险地图', 'nutrition@cdcdc.example.cn', '签署《数据处理协议》',
    '定期安全扫描与渗透测试', '离职后 5 年', '24 小时内通知', '15 个工作日内删除',
  ]) assert.doesNotMatch(all, new RegExp(stale));

  assert.match(source, /医疗健康敏感个人信息/);
  assert.match(source, /阿里云百炼通义千问/);
  assert.match(source, /用户不能自行上传或发布科普文章素材/);
});

test('法律页面按类型展示完整内容，并保留微信隐私保护指引入口', () => {
  let definition;
  const titles = [];
  const toasts = [];
  let privacyOpened = 0;
  const sandbox = {
    Page: value => { definition = value; },
    wx: {
      setNavigationBarTitle: ({ title }) => titles.push(title),
      openPrivacyContract: () => { privacyOpened += 1; },
      showToast: ({ title }) => toasts.push(title),
    },
    require: name => require(path.join(root, 'pages/legal', name)),
  };
  vm.runInNewContext(read('pages/legal/legal.js'), sandbox);
  const page = { ...definition, data: { ...definition.data } };
  page.setData = changes => Object.assign(page.data, changes);

  page.onLoad({ type: 'terms' });
  assert.equal(page.data.type, 'terms');
  assert.equal(page.data.legalDoc.title, '用户服务条款');
  assert.ok(page.data.legalDoc.sections.length >= 8);
  assert.equal(titles.at(-1), '用户服务条款');

  page.onLoad({ type: 'privacy' });
  assert.equal(page.data.legalDoc.title, '隐私政策');
  assert.ok(page.data.legalDoc.sections.length >= 10);
  page.openWechatPrivacy();
  assert.equal(privacyOpened, 1);
  assert.deepEqual(toasts, []);

  const markup = read('pages/legal/legal.wxml');
  const style = read('pages/legal/legal.wxss');
  assert.match(markup, /openWechatPrivacy/);
  assert.match(markup, /legalDoc\.sections/);
  assert.match(style, /font-size:\s*30rpx/);
  assert.match(style, /min-height:\s*94rpx/);
});

test('隐私政策版本升级会要求已登录前重新确认', () => {
  const config = read('utils/config.js');
  assert.match(config, /privacyVersion:\s*'v1\.1-20260916'/);
});
