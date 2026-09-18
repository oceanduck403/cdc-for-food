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
    for (const legacyPage of ['pages/gis-map', 'pages/knowledge']) {
      assert.ok(
        projectConfig.packOptions.ignore.some(item => item.type === 'folder' && item.value === legacyPage),
        `legacy page ${legacyPage} must be excluded from the uploaded package`,
      );
    }

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
