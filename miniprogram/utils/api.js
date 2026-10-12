// utils/api.js
// 后端 API 集中管理
// ─────────────────────────────────────────────────
//  请求由 transport.js 按发布配置统一发送。
// ─────────────────────────────────────────────────
const { networkError } = require('./network-error.js');
const transport = require('./transport.js');

function getBaseUrl() {
  return transport.getDirectBaseUrl();
}

function responseError(res, fallback) {
  const payload = res.data || {};
  const message = typeof payload.message === 'string' && payload.message
    ? payload.message
    : typeof payload.detail === 'string' && payload.detail ? payload.detail : fallback;
  const error = new Error(message);
  error.code = typeof payload.code === 'string' ? payload.code : 'HTTP_ERROR';
  error.statusCode = res.statusCode;
  return error;
}

// 通用请求封装
// 支持两种调用方式：
//   request('/path')                         —— 字符串，快速 GET
//   request({ url, method, data, header, auth })  —— 对象，完整参数
function request(urlOrOptions, maybeMethod, maybeData, maybeHeader, maybeAuth) {
  let options;
  if (typeof urlOrOptions === 'string') {
    // 字符串形式：request('/path', 'POST', data, header, auth)
    options = {
      url: urlOrOptions,
      method: maybeMethod || 'GET',
      data: maybeData,
      header: maybeHeader,
      auth: maybeAuth !== false,
    };
  } else {
    // 对象形式：request({ url, method, data, header, auth })
    options = urlOrOptions || {};
  }

  const { url = '', method = 'GET', data, header = {}, auth = true, timeout = 10000 } = options;
  const token = wx.getStorageSync('token');
  const finalHeader = { 'Content-Type': 'application/json', ...header };
  if (auth && token) {
    finalHeader['Authorization'] = `Bearer ${token}`;
  }
  return new Promise((resolve, reject) => {
    transport.send({
      url,
      method,
      timeout,
      data,
      header: finalHeader,
      success: res => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data);
        } else if (res.statusCode === 401) {
          // token 失效，清空登录态
          // A request from the previous account must not invalidate a newer login.
          if (auth && token && wx.getStorageSync('token') === token) {
            wx.removeStorageSync('token');
            wx.removeStorageSync('userInfo');
            wx.removeStorageSync('role');
            wx.removeStorageSync('profile');
          }
          reject(responseError(res, '请先登录'));
        } else {
          reject(responseError(res, `请求失败 ${res.statusCode}`));
        }
      },
      fail: err => reject(networkError(err)),
    });
  });
}

module.exports = { request, getBaseUrl };
