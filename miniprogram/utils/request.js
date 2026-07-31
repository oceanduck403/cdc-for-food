// utils/request.js
const config = require('./config.js');

function request({ url, method = 'GET', data = {}, header = {}, showLoading = true }) {
  const app = getApp();
  const token = app.globalData.token || wx.getStorageSync('token') || '';

  if (showLoading) {
    wx.showLoading({ title: '加载中', mask: true });
  }

  return new Promise((resolve, reject) => {
    wx.request({
      url: (url.startsWith('http') ? '' : config.apiBase) + url,
      method,
      data,
      header: Object.assign(
        { 'content-type': 'application/json' },
        header,
        token ? { Authorization: `Bearer ${token}` } : {}
      ),
      success(res) {
        if (showLoading) wx.hideLoading();
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data);
        } else if (res.statusCode === 401) {
          app.globalData.token = '';
          wx.removeStorageSync('token');
          wx.showToast({ title: '请重新登录', icon: 'none' });
          reject(res.data);
        } else {
          wx.showToast({
            title: (res.data && res.data.message) || `请求失败 ${res.statusCode}`,
            icon: 'none'
          });
          reject(res.data || res);
        }
      },
      fail(err) {
        if (showLoading) wx.hideLoading();
        wx.showToast({ title: '网络异常', icon: 'none' });
        reject(err);
      }
    });
  });
}

module.exports = { request };