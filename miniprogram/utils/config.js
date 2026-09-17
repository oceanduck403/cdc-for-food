// demo 模式开关：true 时 request 失败不报错，返回 mock 数据
const useMock = false;

// ── 知识库配置（GitHub 托管，GitHub Actions 自动同步）──────────
//    将 enabled 改为 true 启用外部知识库
//    baseUrl 格式：https://raw.githubusercontent.com/{user}/{repo}/main/sync/data
const knowledgeBase = {
  enabled: false,  // 改为 true 启用
  baseUrl: 'https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main/sync/data',
};

// 正式包通过 CloudBase 云托管私有链路访问后端，无需配置 request 合法域名。
// 本地联调如需直连，在开发者工具控制台写入以下两个仅本机生效的配置：
//   wx.setStorageSync('__cdc_api_transport__', 'direct')
//   wx.setStorageSync('__cdc_api_base__', 'http://电脑局域网IP:8000/api/v1')
// 直连覆盖只在开发版生效，体验版和正式版始终使用云托管。
const apiTransport = 'cloud';
const apiBase = '';
const cloud = {
  envId: 'cdc-food-prod-d8gtxkdw22781847c',
  service: 'cdc-food-api',
  apiPrefix: '/api/v1',
};

function accountEnvVersion() {
  try {
    if (typeof wx !== 'undefined' && wx.getAccountInfoSync) {
      return wx.getAccountInfoSync().miniProgram.envVersion || '';
    }
  } catch (_) {}
  return '';
}

function getApiRuntime() {
  const runtime = { mode: apiTransport, apiBase, cloud };
  if (accountEnvVersion() !== 'develop') return runtime;
  try {
    const mode = wx.getStorageSync('__cdc_api_transport__');
    const directBase = wx.getStorageSync('__cdc_api_base__');
    if (mode === 'direct' && /^https?:\/\//i.test(directBase || '')) {
      return { ...runtime, mode: 'direct', apiBase: String(directBase).replace(/\/$/, '') };
    }
  } catch (_) {}
  return runtime;
}

module.exports = {
  apiBase,
  baseUrl: '',
  apiTransport,
  cloud,
  getApiRuntime,
  useMock,
  knowledgeBase,

  // 单日分析次数上限（成本闸口）
  dailyAnalysisLimit: 20,

  // 图片压缩参数
  imageCompress: {
    quality: 70,
    compressedWidth: 1080
  },

  // 隐私协议版本号（升级时强制重弹）
  privacyVersion: 'v1.1-20260916',

  // GIS 地图默认中心：成都市中心
  gisCenter: { latitude: 30.6586, longitude: 104.0648 }
};
