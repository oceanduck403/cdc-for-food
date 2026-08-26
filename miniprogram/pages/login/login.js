// pages/login/login.js
const auth = require('../../utils/auth.js');
const config = require('../../utils/config.js');

const FEATURES = [
  { icon: '📷', name: '拍照识别食物', desc: 'AI 智能分析食物种类与营养成分' },
  { icon: '🗺️', name: '毒蘑菇风险地图', desc: '实时查看周边毒蘑菇分布与中毒高发期' },
  { icon: '📚', name: '知识库', desc: '膳食指南、食品安全与食源性疾病科普' },
  { icon: '👤', name: '个性化健康档案', desc: '基于您的身体数据提供精准营养建议' },
];

Page({
  data: {
    privacyAccepted: false,
    privacyVersion: config.privacyVersion,
    features: FEATURES,
  },

  onLoad() {
    this.setData({ privacyAccepted: auth.isPrivacyAccepted() });
  },

  togglePrivacy() {
    const accepted = !this.data.privacyAccepted;
    if (accepted) auth.acceptPrivacy();
    this.setData({ privacyAccepted: accepted });
  },

  async onWechatLogin() {
    if (!auth.isPrivacyAccepted()) {
      wx.showToast({ title: '请先阅读并同意隐私协议', icon: 'none' });
      return;
    }
    try {
      await auth.loginWithWechat();
      wx.switchTab({ url: '/pages/index/index' });
    } catch (err) {
      console.error('login failed', err);
    }
  },

  openPrivacy() {
    if (wx.openPrivacyContract) {
      wx.openPrivacyContract({ fail: () => {} });
    }
  },

  openTerms() {
    wx.showModal({
      title: '用户服务条款',
      content: '1. 本应用仅提供营养与食品安全科普信息，不构成医疗建议。\n2. 用户需确保提供信息的真实性。\n3. 成都疾控中心保留本服务的解释权。',
      showCancel: false,
      confirmText: '我已知晓',
    });
  }
});
