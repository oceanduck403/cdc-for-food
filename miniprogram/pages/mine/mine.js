// pages/mine/mine.js
const storage = require('../../utils/storage.js');
const config = require('../../utils/config.js');
const navigation = require('../../utils/navigation.js');
const auth = require('../../utils/auth.js');
const { request } = require('../../utils/api.js');
const transport = require('../../utils/transport.js');

function avatarDisplayUrl(avatar) {
  if (!avatar) return '';
  if (avatar.startsWith('//')) return `https:${avatar}`;
  if (/^(https?:|wxfile:|cloud:|data:)/i.test(avatar)) return avatar;
  const base = transport.getDirectBaseUrl ? transport.getDirectBaseUrl() : config.baseUrl;
  return avatar.startsWith('/') && base ? `${base}${avatar}` : '';
}

function confirmModal(options) {
  return new Promise((resolve) => {
    wx.showModal({
      ...options,
      success: resolve,
      fail: () => resolve({ confirm: false }),
    });
  });
}

function clearDeletedAccountData(userId) {
  const id = String(userId || '');
  const fixedKeys = new Set([
    'token', 'role', 'profile', 'userInfo', 'history', 'survey_history',
    'userMarkers',
  ]);
  let keys = [];
  try {
    const info = wx.getStorageInfoSync();
    keys = Array.isArray(info && info.keys) ? info.keys : [];
  } catch (_) {}
  keys.forEach((key) => {
    const belongsToDeletedAccount = id && (
      key === `checkin_records_${id}` ||
      key === `floating_ai_${id}` ||
      key.startsWith(`floating_ai_${id}_quota_`) ||
      key.startsWith(`survey_draft_${id}_`) ||
      key.startsWith(`ai_suggestions_checkin_records_${id}_`)
    );
    if (fixedKeys.has(key) || belongsToDeletedAccount) {
      try { wx.removeStorageSync(key); } catch (_) {}
    }
  });
  // Some test/dev runtimes do not expose getStorageInfoSync.
  fixedKeys.forEach((key) => {
    try { wx.removeStorageSync(key); } catch (_) {}
  });
}

Page({
  data: {
    profile: null,
    isLogin: false,
    bmi: '--',
  },

  onShow() {
    let profile = storage.get('profile');
    let token = storage.get('token');
    // 未登录时展示空档案，不能生成无效的演示 token。
    profile = profile || {};
    if (token && token.startsWith('demo-')) token = '';
    const bmi = this.calcBmi(profile);
    this.setData({ profile: { ...profile, avatarDisplayUrl: avatarDisplayUrl(profile.avatar) }, isLogin: !!token, bmi });
    if (profile.avatar && !this.data.profile.avatarDisplayUrl && transport.resolveMediaUrl) {
      const source = profile.avatar;
      transport.resolveMediaUrl(source).then((resolved) => {
        if (this.data.profile && this.data.profile.avatar === source) {
          this.setData({ 'profile.avatarDisplayUrl': resolved });
        }
      }).catch(() => {});
    }
  },

  calcBmi(profile) {
    if (!profile || !profile.heightCm || !profile.weightKg) return '--';
    const h = profile.heightCm / 100;
    if (h <= 0) return '--';
    return (profile.weightKg / (h * h)).toFixed(1);
  },

  onAvatarError(e) {
    // 头像加载失败时用默认图兜底（静默）
    this.setData({ 'profile.avatarDisplayUrl': '' });
  },

  goProfile() {
    navigation.open('/pages/profile/profile');
  },

  goLogin() {
    navigation.login();
  },

  callSupport() {
    wx.makePhoneCall({ phoneNumber: '87033314', fail: () => {} });
  },

  openPrivacy() {
    navigation.open('/pages/legal/legal?type=privacy');
  },

  openTerms() {
    navigation.open('/pages/legal/legal?type=terms');
  },

  openAbout() {
    wx.showModal({
      title: '关于我们',
      content: '营养与食品安全 AI 小助手 v1.0.0\n\n本应用由成都市疾病预防控制中心提供，仅供营养与食品安全科普使用，不作为诊疗依据。',
      showCancel: false,
      confirmText: '知道了',
    });
  },

  onLogout() {
    wx.showModal({
      title: '退出登录',
      content: '确定要退出当前账号吗？',
      success: (res) => {
        if (res.confirm) {
          auth.logout();
        }
      }
    });
  },

  async onDeleteAccount() {
    if (!this.data.isLogin) return;
    const first = await confirmModal({
      title: '注销账号',
      content: '注销后，您的健康档案、评估、打卡、科普互动和 AI 使用记录将被永久删除，无法恢复。',
      confirmText: '继续注销',
      confirmColor: '#C83E3E',
      cancelText: '暂不注销',
    });
    if (!first.confirm) return;

    const second = await confirmModal({
      title: '最后确认',
      content: '确定永久注销当前账号吗？注销完成后需要重新授权才能使用。',
      confirmText: '确认注销',
      confirmColor: '#C83E3E',
      cancelText: '取消',
    });
    if (!second.confirm) return;

    wx.showLoading({ title: '正在注销', mask: true });
    try {
      const userId = this.data.profile && this.data.profile.id;
      await request({
        url: '/users/me',
        method: 'DELETE',
        data: { confirmation: '注销账号' },
      });
      clearDeletedAccountData(userId);
      wx.hideLoading();
      wx.showToast({ title: '账号已注销', icon: 'success', duration: 800 });
      setTimeout(() => auth.logout(), 500);
    } catch (err) {
      wx.hideLoading();
      wx.showToast({ title: err.message || '注销失败，请稍后重试', icon: 'none' });
    }
  }
});
