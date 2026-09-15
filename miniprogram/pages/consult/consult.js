const navigation = require('../../utils/navigation.js');
// pages/consult/consult.js
// 患者端：与分配的医生一对一聊天（类似美团线上问诊）
const chatApi = require('../../utils/chat.js');
const config = require('../../utils/config.js');
const appointments = require('../../utils/appointments.js');

const app = getApp();

Page({
  data: {
    bookingStatus: 'none', bookingBusy: false, loadError: '', loggedIn: false,
    doctor: null,
    assignmentId: null,
    messages: [],
    userInput: '',
    sending: false,
    loading: true,
    showAiBtn: false, // 底部"问AI"按钮，可切回免费问答
    scrollIntoView: '',
  },

  onLoad() {},
  onShow() {
    this._visible = true;
    const token = wx.getStorageSync('token');
    this.setData({ loggedIn: !!token && !String(token).startsWith('demo-') });
    if (wx.getStorageSync('start_free_appointment')) {
      wx.removeStorageSync('start_free_appointment');
      this.bookAppointment();
    } else this._init();
    clearInterval(this._poll);
    this._poll = setInterval(() => this._init(), 5000);
  },
  onHide() { this._visible = false; clearInterval(this._poll); },
  onUnload() { this.onHide(); },
  onPullDownRefresh() { this._init().finally(() => wx.stopPullDownRefresh()); },
  goLogin() { navigation.open({ url: '/pages/login/login' }); },
  async bookAppointment() {
    if (!this.data.loggedIn) { this.goLogin(); return; }
    if (this.data.bookingBusy) return;
    this.setData({ bookingBusy: true, loadError: '' });
    try { await appointments.book(); await this._init(); }
    catch (err) { this.setData({ loadError: err.message || '预约失败，请重试' }); }
    finally { this.setData({ bookingBusy: false }); }
  },
  async cancelAppointment() {
    if (this.data.bookingBusy) return;
    this.setData({ bookingBusy: true });
    try { await appointments.cancel(); await this._init(); }
    catch (err) { this.setData({ loadError: err.message }); }
    finally { this.setData({ bookingBusy: false }); }
  },
  async _init() {
    if (!this.data.loggedIn) { this.setData({ loading: false, doctor: null, assignmentId: null, messages: [], bookingStatus: 'none' }); return; }
    if (this._refreshing) return;
    this._refreshing = true;
    try {
      const data = await appointments.mine();
      if (!this._visible) return;
      const changed = data.assignment_id !== this.data.assignmentId;
      this.setData({ bookingStatus: data.status, doctor: data.doctor,
        assignmentId: data.assignment_id, loading: false, loadError: '',
        ...(changed ? { messages: [] } : {}) });
      if (data.assignment_id) await this.loadMessages();
    } catch (err) {
      this.setData({ loading: false, loadError: err.message || '加载失败，请重试' });
    } finally { this._refreshing = false; }
  },

  async loadMessages() {
    if (!this.data.assignmentId) return;
    const assignmentId = this.data.assignmentId;
    try {
      const data = await chatApi.fetchMessages({ assignment_id: this.data.assignmentId, limit: 100 });
      if (assignmentId !== this.data.assignmentId || !this._visible) return;
      const base = config.baseUrl || '';
      const messages = (data.messages || []).map(m => ({
        ...m,
        image_url_full: m.image_url ? (m.image_url.startsWith('http') ? m.image_url : base + m.image_url) : null,
        time_str: this.formatTime(m.created_at),
      }));
      const last = messages[messages.length - 1];
      const previous = this.data.messages[this.data.messages.length - 1];
      this.setData({ messages, ...(last && (!previous || last.id !== previous.id)
        ? { scrollIntoView: 'msg-' + (messages.length - 1) } : {}) });
      await chatApi.markRead({ assignment_id: assignmentId });
    } catch (err) {
      console.error('加载消息失败', err);
    }
  },

  onInputChange(e) {
    this.setData({ userInput: e.detail.value });
  },

  async sendMessage() {
    const text = (this.data.userInput || '').trim();
    if (!text || this.data.sending) return;
    if (!this.data.assignmentId) {
      wx.showToast({ title: '正在为您分配医生...', icon: 'none' });
      return;
    }

    this.setData({ sending: true });

    // 乐观插入
    const tempMsg = {
      id: 'tmp-' + Date.now(),
      sender_role: 'patient',
      msg_type: 'text',
      content: text,
      created_at: new Date().toISOString(),
      _pending: true,
    };
    const messages = [...this.data.messages, tempMsg];
    this.setData({
      messages,
      userInput: '',
      scrollIntoView: 'msg-' + (messages.length - 1),
    });

    try {
      await chatApi.sendMessage({
        assignment_id: this.data.assignmentId,
        content: text,
        msg_type: 'text',
      });
      // 重新拉取（拿到真实 id）
      await this.loadMessages();
      await chatApi.markRead({ assignment_id: this.data.assignmentId });
    } catch (err) {
      this.setData({ messages: this.data.messages.filter(m => m.id !== tempMsg.id), userInput: this.data.userInput || text });
      wx.showToast({ title: err.message || '发送失败', icon: 'none' });
    } finally {
      this.setData({ sending: false });
    }
  },

  // 发送图片
  chooseImage() {
    if (!this.data.assignmentId) return;
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      sourceType: ['album', 'camera'],
      success: async (res) => {
        const filePath = res.tempFiles[0].tempFilePath;
        wx.showLoading({ title: '上传中...', mask: true });
        try {
          const imageUrl = await chatApi.uploadChatImage(filePath);
          wx.hideLoading();
          // 发送图片消息（content 携带说明）
          const messages = [...this.data.messages, {
            id: 'tmp-img-' + Date.now(),
            sender_role: 'patient',
            msg_type: 'image',
            content: '[图片]',
            image_url: imageUrl,
            created_at: new Date().toISOString(),
            _pending: true,
          }];
          this.setData({
            messages,
            scrollIntoView: 'msg-' + (messages.length - 1),
          });
          await chatApi.sendMessage({
            assignment_id: this.data.assignmentId,
            content: '[图片]',
            msg_type: 'image',
            image_url: imageUrl,
          });
          await this.loadMessages();
        } catch (err) {
          wx.hideLoading();
          wx.showToast({ title: err.message || '上传失败', icon: 'none' });
        }
      },
    });
  },

  // 跳转到免费AI问答
  goAiConsult() {
    navigation.open({ url: '/pages/consult-ai/consult-ai' });
  },

  formatTime(iso) {
    if (!iso) return '';
    const d = new Date(iso);
    const hh = String(d.getHours()).padStart(2, '0');
    const mm = String(d.getMinutes()).padStart(2, '0');
    return `${hh}:${mm}`;
  },

  previewImage(e) {
    const { url } = e.currentTarget.dataset;
    const all = this.data.messages
      .filter(m => m.image_url)
      .map(m => (config.baseUrl || '') + m.image_url);
    wx.previewImage({ urls: all, current: (config.baseUrl || '') + url });
  },
});
