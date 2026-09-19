const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const builder = require('../../deploy/selfhost/build_miniprogram.js');
const repoRoot = path.resolve(__dirname, '..', '..');

test('正式 API 只接受无凭据、无自定义端口的公网 HTTPS 域名', () => {
  assert.equal(
    builder.validateApiBase('https://1tovalue.cn/cdc-food-api/api/v1/'),
    'https://1tovalue.cn/cdc-food-api/api/v1'
  );
  for (const value of [
    'http://1tovalue.cn/cdc-food-api/api/v1',
    'https://1.14.22.14/cdc-food-api/api/v1',
    'https://[::1]/cdc-food-api/api/v1',
    'https://localhost/api/v1',
    'https://api.example.com/api/v1',
    'https://__FILL_HOST__/api/v1',
    'https://1tovalue.cn:8443/api/v1',
    'https://user:pass@1tovalue.cn/api/v1',
    'https://1tovalue.cn/api/v2',
  ]) {
    assert.throws(() => builder.validateApiBase(value), { name: 'ReleaseConfigError' }, value);
  }
});

test('发布构建写入独立目录，体验版不读取开发者工具本机覆盖', () => {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'cdc-wechat-release-'));
  const outputDir = path.join(temp, 'release');
  try {
    builder.buildRelease({
      repoRoot,
      outputDir,
      apiBase: 'https://1tovalue.cn/cdc-food-api/api/v1',
    });
    const checked = builder.validateRelease(outputDir);
    assert.equal(checked.apiBase, 'https://1tovalue.cn/cdc-food-api/api/v1');
    assert.equal(fs.existsSync(path.join(outputDir, 'miniprogram', 'tests')), false);

    const projectConfig = JSON.parse(fs.readFileSync(path.join(outputDir, 'project.config.json'), 'utf8'));
    for (const legacyPage of [
      'pages/gis-map', 'pages/knowledge', 'pages/consult', 'pages/doctor',
      'pages/doctor-chat', 'pages/doctor-profile', 'pages/dispatch',
    ]) {
      assert.ok(
        projectConfig.packOptions.ignore.some(item => item.type === 'folder' && item.value === legacyPage),
        `legacy page ${legacyPage} must be excluded from the uploaded package`,
      );
    }

    for (const privateFile of [
      'utils/appointments.js', 'utils/chat.js', 'images/consult-online-doctor.jpg',
      'images/consult.png', 'images/consult_active.png',
    ]) {
      assert.ok(
        projectConfig.packOptions.ignore.some(item => item.type === 'file' && item.value === privateFile),
        `clinical file ${privateFile} must be excluded from the uploaded package`,
      );
    }

    const appConfig = JSON.parse(fs.readFileSync(path.join(outputDir, 'miniprogram', 'app.json'), 'utf8'));
    for (const clinicalPage of [
      'pages/consult/consult', 'pages/doctor/doctor', 'pages/doctor-chat/doctor-chat',
      'pages/doctor-profile/doctor-profile', 'pages/dispatch/dispatch',
    ]) assert.equal(appConfig.pages.includes(clinicalPage), false, clinicalPage);
    assert.deepEqual(appConfig.tabBar.list[2], {
      pagePath: 'pages/consult-ai/consult-ai',
      text: 'AI科普',
      iconPath: 'images/ui/chat-muted.png',
      selectedIconPath: 'images/ui/chat-tab-selected.png',
    });

    const publicCopy = [
      'pages/login/login.js', 'pages/login/login.wxml',
      'pages/consult-ai/consult-ai.json', 'pages/consult-ai/consult-ai.wxml',
      'pages/mine/mine.js', 'pages/survey/survey.wxml', 'utils/legal-content.js',
    ].map(file => fs.readFileSync(path.join(outputDir, 'miniprogram', file), 'utf8')).join('\n');
    assert.doesNotMatch(publicCopy, /医生在线指导|免费预约|提交预约|匹配医生|医患|医生登录|管理员入口/);
    assert.match(publicCopy, /营养与食品安全科普/);
    assert.match(publicCopy, /不作为诊疗依据/);

    const configPath = path.join(outputDir, 'miniprogram', 'utils', 'config.js');
    const runtimePath = path.join(outputDir, 'miniprogram', 'utils', 'release-runtime.js');
    delete require.cache[require.resolve(configPath)];
    delete require.cache[require.resolve(runtimePath)];
    global.wx = {
      getAccountInfoSync: () => ({ miniProgram: { envVersion: 'trial' } }),
      getStorageSync: key => key === '__cdc_api_base__' ? 'http://10.0.0.8:8000/api/v1' : 'direct',
    };
    const config = require(configPath);
    assert.deepEqual(config.getApiRuntime(), {
      mode: 'direct',
      apiBase: 'https://1tovalue.cn/cdc-food-api/api/v1',
      cloud: { envId: '', service: '', apiPrefix: '/api/v1' },
    });
  } finally {
    delete global.wx;
    fs.rmSync(temp, { recursive: true, force: true });
  }
});

test('开发版仍可使用本机存储覆盖发布地址', () => {
  const originalWx = global.wx;
  try {
    global.wx = {
      getAccountInfoSync: () => ({ miniProgram: { envVersion: 'develop' } }),
      getStorageSync: key => key === '__cdc_api_base__' ? 'http://192.168.1.20:8000/api/v1/' : 'direct',
    };
    const configPath = path.join(repoRoot, 'miniprogram', 'utils', 'config.js');
    delete require.cache[require.resolve(configPath)];
    const config = require(configPath);
    assert.equal(config.getApiRuntime().mode, 'direct');
    assert.equal(config.getApiRuntime().apiBase, 'http://192.168.1.20:8000/api/v1');
  } finally {
    global.wx = originalWx;
  }
});
