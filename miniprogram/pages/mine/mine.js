// pages/mine/mine.js
const storage = require('../../utils/storage.js');

Page({
  data: {
    profile: null,
    isLogin: false
  },

  onShow() {
    this.setData({
      profile: storage.get('profile'),
      isLogin: !!storage.get('token')
    });
  },

  goProfile() {
    wx.navigateTo({ url: '/pages/profile/profile' });
  },

  goLogin() {
    wx.navigateTo({ url: '/pages/login/login' });
  },

  callSupport() {
    wx.makePhoneCall({ phoneNumber: '87033314', fail: () => {} });
  },

  onLogout() {
    storage.clearUserData();
    this.setData({ isLogin: false, profile: null });
    wx.showToast({ title: '已退出' });
  }
});