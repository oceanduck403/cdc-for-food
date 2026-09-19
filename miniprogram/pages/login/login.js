// pages/login/login.js
const auth = require('../../utils/auth.js');
const navigation = require('../../utils/navigation.js');

const FEATURES = [
  { icon: 'camera', name: '膳食拍照识别', desc: '了解食物与营养信息' },
  { icon: 'survey', name: '健康评估', desc: '记录饮食与生活习惯' },
  { icon: 'book', name: '科普互动', desc: '阅读营养与食品安全知识' },
  { icon: 'robot', name: 'AI 科普问答', desc: '获取通俗易懂的科普参考' },
];

Page({
  data: {
    privacyAccepted: false,
    features: FEATURES,
  },

  onLoad() {
    this.setData({ privacyAccepted: auth.isPrivacyAccepted() });
    const token = auth.getToken();
    if (token && !token.startsWith('demo-') && auth.getRole() === 'patient') {
      this._enterUserHome();
    }
  },

  togglePrivacy() {
    const accepted = !this.data.privacyAccepted;
    if (accepted) auth.acceptPrivacy();
    this.setData({ privacyAccepted: accepted });
  },

  async onWechatLogin() {
    if (!this._checkPrivacy()) return;
    wx.showLoading({ title: '登录中...', mask: true });
    try {
      await auth.loginWithWechat();
      wx.hideLoading();
      wx.showToast({ title: '登录成功', icon: 'success' });
      setTimeout(() => this._enterUserHome(), 600);
    } catch (err) {
      wx.hideLoading();
      wx.showToast({ title: err.message || '登录失败', icon: 'none' });
    }
  },

  _enterUserHome() {
    wx.switchTab({
      url: '/pages/survey/survey',
      fail: () => wx.reLaunch({ url: '/pages/survey/survey' }),
    });
  },

  _checkPrivacy() {
    if (!auth.isPrivacyAccepted()) {
      wx.showToast({ title: '请先阅读并同意隐私协议', icon: 'none' });
      return false;
    }
    return true;
  },

  openPrivacy() {
    navigation.open('/pages/legal/legal?type=privacy');
  },

  openTerms() {
    navigation.open('/pages/legal/legal?type=terms');
  },
});
