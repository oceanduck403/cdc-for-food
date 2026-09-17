// 发布脚本只会在 build/ 产物中替换本文件。
// 源码保持未配置状态，防止误把开发地址或旧云环境打入体验版/正式版。
module.exports = Object.freeze({
  generated: false,
  apiTransport: 'unconfigured',
  apiBase: '',
  cloud: Object.freeze({
    envId: '',
    service: '',
    apiPrefix: '/api/v1',
  }),
});
