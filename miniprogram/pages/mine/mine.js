// pages/mine/mine.js
const storage = require('../../utils/storage.js');
const config = require('../../utils/config.js');
const navigation = require('../../utils/navigation.js');
const auth = require('../../utils/auth.js');

function avatarDisplayUrl(avatar) {
  if (!avatar) return '';
  if (avatar.startsWith('//')) return `https:${avatar}`;
  if (/^(https?:|wxfile:|cloud:|data:)/i.test(avatar)) return avatar;
  return avatar.startsWith('/') && config.baseUrl ? `${config.baseUrl}${avatar}` : avatar;
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
  }
});
