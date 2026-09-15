// utils/auth.js
const { request } = require('./api.js');
const config = require('./config.js');

// ──────────────────────────────────────────────
// 患者：微信登录
// ──────────────────────────────────────────────
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
          auth: false,
        })
          .then((data) => {
            _saveSession(data, 'patient');
            resolve(data);
          })
          .catch(reject);
      },
      fail: reject,
    });
  });
}

// ──────────────────────────────────────────────
// 医生 / 管理员：账号密码登录
// ──────────────────────────────────────────────
function loginWithAccount({ username, password, role }) {
  return request({
    url: '/auth/account-login',
    method: 'POST',
    data: { username, password, role },
    auth: false,
  }).then((data) => {
    _saveSession(data, role);
    return data;
  });
}

// ──────────────────────────────────────────────
// 通用：保存会话
// ──────────────────────────────────────────────
function _saveSession(data, role) {
  const app = getApp();
  app.globalData.token = data.token;
  app.globalData.role = data.role || role;
  const profile = { ...(data.profile || {}), role: data.role || role };
  app.globalData.profile = profile;
  wx.setStorageSync('token', data.token);
  wx.setStorageSync('role', data.role || role);
  wx.setStorageSync('profile', profile);
  wx.setStorageSync('userInfo', profile);
}

// ──────────────────────────────────────────────
// 其他
// ──────────────────────────────────────────────
function bindPhone(phoneCode) {
  return request({
    url: '/auth/bind-phone',
    method: 'POST',
    data: { code: phoneCode },
  });
}

function getRole() {
  return wx.getStorageSync('role') || '';
}

function getToken() {
  return wx.getStorageSync('token') || '';
}

function isLoggedIn() {
  return !!getToken();
}

// App.onShow 会调用此方法；后台请求失败不能中断小程序生命周期。
async function refreshDailyQuota(app) {
  const token = getToken();
  if (!token || token.startsWith('demo-')) return;
  try {
    const quota = await request('/users/me/quota');
    if (quota && Number.isFinite(Number(quota.used))) {
      app.globalData.dailyAnalysisCount = Math.max(0, Number(quota.used));
    }
  } catch (err) {
    console.warn('[auth] 每日次数暂未更新:', err.message || '网络异常');
  }
}

function logout(destination = '/pages/login/login') {
  const app = getApp();
  app.globalData.token = '';
  app.globalData.role = '';
  app.globalData.profile = {};
  app.globalData.userInfo = null;
  wx.removeStorageSync('start_free_appointment');
  wx.removeStorageSync('token');
  wx.removeStorageSync('role');
  wx.removeStorageSync('profile');
  wx.removeStorageSync('userInfo');
  wx.reLaunch({ url: destination });
}

function acceptPrivacy() {
  wx.setStorageSync('privacy_accepted', config.privacyVersion);
}

function isPrivacyAccepted() {
  return wx.getStorageSync('privacy_accepted') === config.privacyVersion;
}

module.exports = {
  loginWithWechat,
  loginWithAccount,
  bindPhone,
  acceptPrivacy,
  isPrivacyAccepted,
  getRole,
  getToken,
  isLoggedIn,
  refreshDailyQuota,
  logout,
};
