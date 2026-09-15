// pages/doctor-profile/doctor-profile.js
const auth = require('../../utils/auth.js');

Page({
  data: {
    profile: {},
  },

  onLoad() {
    this.setData({ profile: wx.getStorageSync('profile') || {} });
  },

  async logout() {
    const res = await new Promise(r => wx.showModal({ title: '退出登录', content: '确定退出吗？', success: r }));
    if (res.confirm) {
      auth.logout();
    }
  },
});
