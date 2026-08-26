// utils/config.js
// demo 默认 useMock=true：所有 request() 失败时静默 fallback 到 utils/mock.js
// 上线前请改为 false 并配置 https 后端域名（公众平台 → 开发管理 → 服务器域名）。
module.exports = {
  // ── 阿里云百炼（千问 VL）配置 ────────────────────────────────
  //   API Key：请前往 https://bailian.console.aliyun.com/ 申请
  //   region：cn-beijing（默认）/ ap-southeast-1 / ap-northeast-1 等
  qwen: {
    apiKey: 'sk-ws-H.ERXRHIP.dK8t.MEUCIQC-ggM78uOxbB4xRwZdKleywVt7_4vWh6X7V9OjoM2ndQIgGkBxdfUwWTkz9dTVRDtVkw_YcTpka5OCpf4PTdtVZOE',
    baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    model: 'qwen-vl-plus',         // qwen-vl-plus | qwen-vl-max | qwen3-vl-plus 等
  },

  // ── 后端基础地址（生产环境通过微信公众平台配置 request 合法域名）─────────
  apiBase: 'https://api.example-cdc.local/v1',

  // demo 模式开关：true 时 request 失败不报错，返回 mock 数据
  useMock: true,

  // ── 知识库配置（GitHub 托管，GitHub Actions 自动同步）──────────
  //    将 enabled 改为 true 启用外部知识库
  //    baseUrl 格式：https://raw.githubusercontent.com/{user}/{repo}/main/sync/data
  knowledgeBase: {
    enabled: false,  // 改为 true 启用
    baseUrl: 'https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main/sync/data',
  },

  // ── 商用菜品识别 API 走小程序云函数中转，避免暴露密钥
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
