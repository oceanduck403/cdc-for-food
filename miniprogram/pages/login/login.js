// pages/login/login.js
const auth = require('../../utils/auth.js');
const config = require('../../utils/config.js');

Page({
  data: {
    privacyAccepted: false,
    privacyVersion: config.privacyVersion
  },

  onLoad() {
    this.setData({ privacyAccepted: auth.isPrivacyAccepted() });
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

  onAcceptPrivacy() {
    auth.acceptPrivacy();
    this.setData({ privacyAccepted: true });
  },

  openPrivacy() {
    if (wx.openPrivacyContract) {
      wx.openPrivacyContract({ fail: () => {} });
    }
  }
});