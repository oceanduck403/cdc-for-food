// pages/login/login.js
const auth = require('../../utils/auth.js');
const navigation = require('../../utils/navigation.js');

const FEATURES = [
  { icon: 'camera', name: '拍照识别食物', desc: 'AI 智能分析食物种类与营养成分' },
  { icon: 'search', name: '毒蘑菇风险地图', desc: '实时查看周边毒蘑菇分布与中毒高发期' },
  { icon: 'book', name: '知识库', desc: '膳食指南、食品安全与食源性疾病科普' },
  { icon: 'user', name: '个性化健康档案', desc: '基于您的身体数据提供精准营养建议' },
];

Page({
  data: {
    privacyAccepted: false,
    currentRole: 'patient', // patient / doctor
    features: FEATURES,
    // 医生端
    doctorUsername: '',
    doctorPassword: '',
  },

  onLoad(options = {}) {
    this.setData({ privacyAccepted: auth.isPrivacyAccepted(), currentRole: options.role === 'doctor' ? 'doctor' : 'patient' });
    const token = auth.getToken();
    const role = auth.getRole();
    if (token && !token.startsWith('demo-') && ['patient', 'doctor', 'admin'].includes(role)) this._navigateByRole(role);
  },

  // ─── 角色切换 ───────────────────────────────────
  switchRole(e) {
    const { role } = e.currentTarget.dataset;
    if (role === 'admin') { navigation.login('admin'); return; }
    this.setData({ currentRole: role });
  },

  togglePrivacy() {
    const accepted = !this.data.privacyAccepted;
    if (accepted) auth.acceptPrivacy();
    this.setData({ privacyAccepted: accepted });
  },

  // ─── 患者端：微信登录 ──────────────────────────
  async onWechatLogin() {
    if (!this._checkPrivacy()) return;
    wx.showLoading({ title: '登录中...', mask: true });
    try {
      await auth.loginWithWechat();
      wx.hideLoading();
      wx.showToast({ title: '登录成功', icon: 'success' });
      setTimeout(() => this._navigateByRole('patient'), 600);
    } catch (err) {
      wx.hideLoading();
      wx.showToast({ title: err.message || '登录失败', icon: 'none' });
    }
  },

  // ─── 医生端登录 ──────────────────────────────────
  onDoctorUsernameInput(e) {
    this.setData({ doctorUsername: e.detail.value });
  },

  onDoctorPasswordInput(e) {
    this.setData({ doctorPassword: e.detail.value });
  },

  async onDoctorLogin() {
    if (!this._checkPrivacy()) return;
    wx.showLoading({ title: '登录中...', mask: true });
    try {
      await auth.loginWithAccount({
        username: this.data.doctorUsername,
        password: this.data.doctorPassword,
        role: 'doctor',
      });
      wx.hideLoading();
      wx.showToast({ title: '登录成功', icon: 'success' });
      setTimeout(() => this._navigateByRole('doctor'), 600);
    } catch (err) {
      wx.hideLoading();
      wx.showToast({ title: err.message || '登录失败', icon: 'none' });
    }
  },

  // ─── 管理员入口 ──────────────────────────────────
  goToAdminLogin() {
    navigation.login('admin');
  },

  // ─── 跳转 ────────────────────────────────────────
  _navigateByRole(role) {
    if (role === 'admin') {
      wx.reLaunch({ url: '/pages/admin/admin', fail: navigation.report });
      return;
    }
    if (role === 'doctor') {
      wx.reLaunch({ url: '/pages/doctor/doctor', fail: navigation.report });
      return;
    }
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
    if (wx.openPrivacyContract) {
      wx.openPrivacyContract({ fail: () => {} });
    }
  },

  openTerms() {
    wx.showModal({
      title: '用户服务条款',
      content: '1. 本应用由成都市疾病预防控制中心提供，仅供营养与食品安全科普使用，不作为诊疗依据。\n2. 用户需确保提供信息的真实性。\n3. 成都市疾病预防控制中心保留本服务的解释权。',
      showCancel: false,
      confirmText: '我已知晓',
    });
  },
});
