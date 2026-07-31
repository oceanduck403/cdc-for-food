// utils/config.js
// demo 默认 useMock=true：所有 request() 失败时静默 fallback 到 utils/mock.js
// 上线前请改为 false 并配置 https 后端域名（公众平台 → 开发管理 → 服务器域名）。
module.exports = {
  // 后端基础地址（生产环境通过微信公众平台配置 request 合法域名）
  apiBase: 'https://api.example-cdc.local/v1',

  // demo 模式开关：true 时 request 失败不报错，返回 mock 数据
  useMock: true,

  // 商用菜品识别 API 走小程序云函数中转，避免暴露密钥
  visionGateway: '/api/v1/vision/dish',

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
