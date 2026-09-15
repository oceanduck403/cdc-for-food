// pages/admin-login/admin-login.js
const auth = require('../../utils/auth.js');
const navigation = require('../../utils/navigation.js');

Page({
  data: {
    username: '',
    password: '',
  },

  onUsernameInput(e) {
    this.setData({ username: e.detail.value });
  },

  onPasswordInput(e) {
    this.setData({ password: e.detail.value });
  },

  async onLogin() {
    if (!this.data.username || !this.data.password) {
      wx.showToast({ title: '请输入账号和密码', icon: 'none' });
      return;
    }
    wx.showLoading({ title: '登录中...', mask: true });
    try {
      await auth.loginWithAccount({
        username: this.data.username,
        password: this.data.password,
        role: 'admin',
      });
      wx.hideLoading();
      wx.showToast({ title: '登录成功', icon: 'success' });
      setTimeout(() => {
        wx.reLaunch({ url: '/pages/admin/admin', fail: navigation.report });
      }, 600);
    } catch (err) {
      wx.hideLoading();
      wx.showToast({ title: err.message || '登录失败', icon: 'none' });
    }
  },

  goBack() {
    wx.navigateBack({ fail: () => navigation.login() });
  },
});
