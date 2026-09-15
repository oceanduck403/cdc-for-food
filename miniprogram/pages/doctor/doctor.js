const navigation = require('../../utils/navigation.js');
// pages/doctor/doctor.js
// 医生端主页：患者列表（支持搜索）
const chatApi = require('../../utils/chat.js');
const auth = require('../../utils/auth.js');

Page({
  data: {
    profile: {},
    patients: [],
    keyword: '',
    loading: true,
    loadError: "",
  },

  onLoad() {
    const profile = wx.getStorageSync('profile') || {};
    this.setData({ profile });
  },

  onShow() {
    if (auth.getRole() !== 'doctor' || !auth.getToken()) {
      wx.reLaunch({ url: '/pages/login/login?role=doctor', fail: navigation.report });
      return;
    }
    this.setData({ profile: wx.getStorageSync('profile') || {} });
    require('../../utils/appointments.js').heartbeat().catch(() => {});
    clearInterval(this._poll);
    this._poll = setInterval(() => this.loadPatients(), 5000);
    // 每次显示刷新
    this.loadPatients();
  },

  onHide() { clearInterval(this._poll); },
  onUnload() { this.onHide(); },

  onPullDownRefresh() {
    this.loadPatients().then(() => wx.stopPullDownRefresh());
  },

  async loadPatients() {
    const token = auth.getToken();
    try {
      const data = await chatApi.fetchDoctorPatients(this.data.keyword);
      if (auth.getToken() !== token) return;
      this.setData({
        patients: (data.patients || []).map(item => ({...item, lastMessageTime: this.formatTime(item.last_message_at)})),
        loadError: '',
        loading: false,
      });
    } catch (err) {
      console.error('加载患者失败', err);
      if (auth.getToken() && auth.getToken() !== token) return;
      this.setData({ loading: false, loadError: err.message || '患者列表加载失败，请重试' });
      if (!auth.getToken()) {
        wx.showToast({ title: '登录已过期', icon: 'none' });
        auth.logout();
      }
    }
  },

  onKeywordInput(e) {
    this.setData({ keyword: e.detail.value });
  },

  onSearch() {
    this.loadPatients();
  },

  clearKeyword() {
    this.setData({ keyword: '' });
    this.loadPatients();
  },

  goChat(e) {
    const { assignmentid, patientid, patientname } = e.currentTarget.dataset;
    navigation.open({
      url: `/pages/doctor-chat/doctor-chat?assignment_id=${assignmentid}&patient_id=${patientid}&patient_name=${encodeURIComponent(patientname)}`,
    });
  },

  goProfile() {
    navigation.open({ url: '/pages/doctor-profile/doctor-profile' });
  },

  async logout() {
    const res = await new Promise(r => wx.showModal({
      title: '退出登录',
      content: '确定退出吗？',
      success: r,
    }));
    if (res.confirm) {
      auth.logout();
    }
  },

  formatTime(iso) {
    if (!iso) return '';
    const d = new Date(iso);
    const now = new Date();
    const diff = (now - d) / 1000;
    if (diff < 60) return '刚刚';
    if (diff < 3600) return `${Math.floor(diff / 60)}分钟前`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}小时前`;
    if (diff < 604800) return `${Math.floor(diff / 86400)}天前`;
    return `${d.getMonth() + 1}/${d.getDate()}`;
  },
});
