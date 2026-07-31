// utils/auth.js
const { request } = require('./request.js');
const config = require('./config.js');

function loginWithWechat() {
  return new Promise((resolve, reject) => {
    wx.login({
      success: ({ code }) => {
        if (!code) {
          reject(new Error('微信登录失败：未返回 code'));
          return;
        }
        request({
          url: '/auth/wechat',
          method: 'POST',
          data: { code },
          showLoading: false
        })
          .then((data) => {
            const app = getApp();
            app.globalData.token = data.token;
            wx.setStorageSync('token', data.token);
            wx.setStorageSync('profile', data.profile || {});
            resolve(data);
          })
          .catch(reject);
      },
      fail: reject
    });
  });
}

function bindPhone(phoneCode) {
  return request({
    url: '/auth/bind-phone',
    method: 'POST',
    data: { code: phoneCode }
  });
}

function acceptPrivacy() {
  wx.setStorageSync('privacy_accepted', config.privacyVersion);
}

function isPrivacyAccepted() {
  return wx.getStorageSync('privacy_accepted') === config.privacyVersion;
}

function refreshDailyQuota(app) {
  if (!app.globalData.token) return;
  request({ url: '/users/me/quota', showLoading: false })
    .then((data) => {
      app.globalData.dailyAnalysisCount = data.used || 0;
    })
    .catch(() => {});
}

module.exports = {
  loginWithWechat,
  bindPhone,
  acceptPrivacy,
  isPrivacyAccepted,
  refreshDailyQuota
};