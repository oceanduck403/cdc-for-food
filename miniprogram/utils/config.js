// demo 模式开关：true 时 request 失败不报错，返回 mock 数据
const useMock = false;

// ── 知识库配置（GitHub 托管，GitHub Actions 自动同步）──────────
//    将 enabled 改为 true 启用外部知识库
//    baseUrl 格式：https://raw.githubusercontent.com/{user}/{repo}/main/sync/data
const knowledgeBase = {
  enabled: false,  // 改为 true 启用
  baseUrl: 'https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main/sync/data',
};

// 同一 Wi-Fi 下的手机联调地址；电脑 IP 改变时只需修改这里。
// 体验版/正式版须换成已配置合法域名的公网 HTTPS 服务。
const apiBase = 'http://192.168.0.102:8000/api/v1';

module.exports = {
  apiBase,
  baseUrl: apiBase.replace(/\/api\/v1\/?$/, ''),
  useMock,
  knowledgeBase,

  // ── 商用菜品识别 API 走小程序云函数中转，避免暴露密钥
  visionGateway: '/vision/dish',

  // 单日分析次数上限（成本闸口）
  dailyAnalysisLimit: 20,

  // 图片压缩参数
  imageCompress: {
    quality: 70,
    compressedWidth: 1080
  },

  // 隐私协议版本号（升级时强制重弹）
  privacyVersion: 'v1.0-202607',

  // GIS 地图默认中心：成都市中心
  gisCenter: { latitude: 30.6586, longitude: 104.0648 }
};
