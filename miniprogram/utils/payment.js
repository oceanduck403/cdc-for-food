// utils/payment.js
// 微信支付工具类

/**
 * 微信支付配置
 */
const paymentConfig = {
  // 微信小程序AppID
  appId: '',

  // 设置为true启用模拟支付（开发环境）
  mockMode: true,
};

/**
 * 初始化支付配置
 * @param {Object} config - 配置对象 { appId, mockMode }
 */
function initPayment(config) {
  if (config.appId) {
    paymentConfig.appId = config.appId;
  }
  if (config.mockMode !== undefined) {
    paymentConfig.mockMode = config.mockMode;
  }
}

/**
 * 发起微信支付
 * @param {Object} paymentParams - 支付参数（从服务端获取）
 * @returns {Promise} - 返回支付结果
 */
function requestPayment(paymentParams) {
  return new Promise((resolve, reject) => {
    // 模拟支付模式（开发环境）
    if (paymentConfig.mockMode || paymentParams.mock) {
      console.log('[Payment] 模拟支付模式:', paymentParams);
      resolve({ errMsg: 'requestPayment:ok', mock: true });
      return;
    }

    // 真实微信支付
    wx.requestPayment({
      timeStamp: paymentParams.timeStamp,
      nonceStr: paymentParams.nonceStr,
      package: paymentParams.package,
      signType: paymentParams.signType || 'MD5',
      paySign: paymentParams.paySign,
      success: (res) => {
        console.log('[Payment] 支付成功', res);
        resolve(res);
      },
      fail: (err) => {
        console.log('[Payment] 支付失败', err);
        reject(err);
      }
    });
  });
}

/**
 * 检查是否支持微信支付
 * @returns {Boolean}
 */
function isPaymentSupported() {
  // 在小程序环境中检查
  return typeof wx !== 'undefined' && wx.requestPayment !== undefined;
}

/**
 * 获取支付配置
 * @returns {Object}
 */
function getConfig() {
  return { ...paymentConfig };
}

module.exports = {
  initPayment,
  requestPayment,
  isPaymentSupported,
  getConfig,
};
