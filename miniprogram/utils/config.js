// utils/config.js
module.exports = {
  // 后端基础地址（生产环境通过微信公众平台配置 request 合法域名）
  apiBase: 'https://api.example-cdc.local/v1',

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