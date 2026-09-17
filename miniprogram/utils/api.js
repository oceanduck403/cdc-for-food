// utils/api.js
// 后端 API 集中管理
// ─────────────────────────────────────────────────
//  正式版由 transport.js 统一走 CloudBase 私有链路；开发版可临时直连。
// ─────────────────────────────────────────────────
const { networkError } = require('./network-error.js');
const transport = require('./transport.js');

function getBaseUrl() {
  return transport.getDirectBaseUrl();
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

  const { url = '', method = 'GET', data, header = {}, auth = true } = options;
  const token = wx.getStorageSync('token');
  const finalHeader = { 'Content-Type': 'application/json', ...header };
  if (auth && token) {
    finalHeader['Authorization'] = `Bearer ${token}`;
  }
  return new Promise((resolve, reject) => {
    transport.send({
      url,
      method,
      timeout: 10000,
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
          reject(new Error(res.data?.detail || '请先登录'));
        } else {
          reject(new Error(res.data?.detail || `请求失败 ${res.statusCode}`));
        }
      },
      fail: err => reject(networkError(err)),
    });
  });
}

module.exports = { request, getBaseUrl };
