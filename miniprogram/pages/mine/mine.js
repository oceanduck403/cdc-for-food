// pages/mine/mine.js
const storage = require('../../utils/storage.js');
const mock = require('../../utils/mock.js');

Page({
  data: {
    profile: null,
    isLogin: false
  },

  onShow() {
    let profile = storage.get('profile');
    let token = storage.get('token');
    // demo 模式：第一次进入时预填演示档案，方便跑通
    if (!profile) {
      profile = mock.profile;
      storage.set('profile', profile);
    }
    if (!token) {
      token = 'demo-token';
      storage.set('token', token);
    }
    this.setData({ profile, isLogin: !!token });
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
