const { privacy, terms } = require('../../utils/legal-content.js');

Page({
  data: {
    type: 'privacy',
    legalDoc: privacy,
  },

  onLoad(options = {}) {
    const type = options.type === 'terms' ? 'terms' : 'privacy';
    const legalDoc = type === 'terms' ? terms : privacy;
    this.setData({ type, legalDoc });
    wx.setNavigationBarTitle({ title: legalDoc.title });
  },

  openWechatPrivacy() {
    if (!wx.openPrivacyContract) {
      wx.showToast({ title: '请升级微信后查看', icon: 'none' });
      return;
    }
    wx.openPrivacyContract({
      fail: () => wx.showToast({ title: '暂时无法打开，请稍后重试', icon: 'none' }),
    });
  },
});
