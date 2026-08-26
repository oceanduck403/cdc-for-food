// pages/mine/mine.js
const storage = require('../../utils/storage.js');
const mock = require('../../utils/mock.js');
const config = require('../../utils/config.js');

Page({
  data: {
    profile: null,
    isLogin: false,
    isVip: false,
    remaining: 0,
    bmi: '--',
  },

  onShow() {
    let profile = storage.get('profile');
    let token = storage.get('token');
    // demo 模式：第一次进入时预填演示档案
    if (!profile) {
      profile = mock.profile;
      storage.set('profile', profile);
    }
    if (!token) {
      token = 'demo-token';
      storage.set('token', token);
    }
    const bmi = this.calcBmi(profile);
    const isVip = profile && profile.isVip;
    const remaining = profile && profile.remainingCount !== undefined
      ? profile.remainingCount
      : config.dailyAnalysisLimit;
    this.setData({ profile, isLogin: !!token, bmi, isVip, remaining });
  },

  calcBmi(profile) {
    if (!profile || !profile.heightCm || !profile.weightKg) return '--';
    const h = profile.heightCm / 100;
    if (h <= 0) return '--';
    return (profile.weightKg / (h * h)).toFixed(1);
  },

  onAvatarError(e) {
    // 头像加载失败时用默认图兜底（静默）
    this.setData({ 'profile.avatar': '' });
  },

  goProfile() {
    wx.navigateTo({ url: '/pages/profile/profile' });
  },

  goPayment() {
    wx.navigateTo({ url: '/pages/payment/payment' });
  },

  goLogin() {
    wx.navigateTo({ url: '/pages/login/login' });
  },

  callSupport() {
    wx.makePhoneCall({ phoneNumber: '87033314', fail: () => {} });
  },

  openPrivacy() {
    wx.showModal({
      title: '隐私协议',
      content: '本应用严格遵守《个人信息保护法》，仅收集必要的健康数据用于个性化营养建议，数据存储于您授权的服务端，不对外共享。',
      showCancel: false,
      confirmText: '我已知晓',
    });
  },

  openAbout() {
    wx.showModal({
      title: '关于我们',
      content: '成都市疾病预防控制中心\n营养与食品安全 AI 小助手 v1.0.0\n\n本应用由成都市疾病预防控制中心委托开发，提供营养与食品安全科普信息，不作为诊疗依据。',
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
          storage.clearUserData();
          this.setData({ isLogin: false, profile: null, bmi: '--' });
          wx.showToast({ title: '已退出' });
        }
      }
    });
  }
});
