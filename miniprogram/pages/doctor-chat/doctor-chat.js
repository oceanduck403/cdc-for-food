// pages/doctor-chat/doctor-chat.js
// 医生与患者的聊天窗口（含会诊邀请）
const chatApi = require('../../utils/chat.js');
const config = require('../../utils/config.js');

Page({
  data: {
    assignmentId: 0,
    patientId: 0,
    patientName: '',
    patientInfo: null,
    messages: [],
    userInput: '',
    sending: false,
    loading: true,
    scrollIntoView: '',
    showConsultPanel: false,
    availableDoctors: [],
  },

  onLoad(options) {
    this.setData({
      assignmentId: parseInt(options.assignment_id),
      patientId: parseInt(options.patient_id),
      patientName: decodeURIComponent(options.patient_name || ''),
    });
    this._init();
  },

  onShow() {
    clearInterval(this._poll);
    this._poll = setInterval(() => this.loadMessages(), 5000);
    if (this.data.assignmentId) {
      this.loadMessages();
    }
  },

  onHide() { clearInterval(this._poll); },
  onUnload() { this.onHide(); },

  onPullDownRefresh() {
    this.loadMessages().then(() => wx.stopPullDownRefresh());
  },

  async _init() {
    await Promise.all([this.loadMessages(), this.loadPatientInfo()]);
  },

  async loadPatientInfo() {
    try {
      const data = await chatApi.fetchPatientDetail(this.data.patientId);
      this.setData({ patientInfo: data.patient });
    } catch (err) {
      console.error('加载患者信息失败', err);
    }
  },

  async loadMessages() {
    if (!this.data.assignmentId) return;
    try {
      const data = await chatApi.fetchMessages({ assignment_id: this.data.assignmentId, limit: 100 });
      const base = config.baseUrl || '';
      const messages = (data.messages || []).map(m => ({
        ...m,
        image_url_full: m.image_url ? (m.image_url.startsWith('http') ? m.image_url : base + m.image_url) : null,
        time_str: this.formatTime(m.created_at),
      }));
      this.setData({
        messages,
        loading: false,
        scrollIntoView: 'msg-' + (messages.length - 1),
      });
      // 标记已读
      await chatApi.markRead({ assignment_id: this.data.assignmentId });
    } catch (err) {
      console.error('加载消息失败', err);
      this.setData({ loading: false });
    }
  },

  onInputChange(e) {
    this.setData({ userInput: e.detail.value });
  },

  async sendMessage() {
    const text = (this.data.userInput || '').trim();
    if (!text || this.data.sending) return;

    this.setData({ sending: true });

    const tempMsg = {
      id: 'tmp-' + Date.now(),
      sender_role: 'doctor',
      msg_type: 'text',
      content: text,
      created_at: new Date().toISOString(),
      time_str: this.formatTime(new Date()),
      _pending: true,
    };
    let messages = [...this.data.messages, tempMsg];
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
      await this.loadMessages();
    } catch (err) {
      wx.showToast({ title: err.message || '发送失败', icon: 'none' });
    } finally {
      this.setData({ sending: false });
    }
  },

  // 图片消息
  chooseImage() {
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
          let messages = [...this.data.messages, {
            id: 'tmp-img-' + Date.now(),
            sender_role: 'doctor',
            msg_type: 'image',
            content: '[图片]',
            image_url: imageUrl,
            image_url_full: imageUrl,
            created_at: new Date().toISOString(),
            time_str: this.formatTime(new Date()),
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

  // 打开会诊邀请
  async openConsultPanel() {
    this.setData({ showConsultPanel: true });
    try {
      const data = await chatApi.fetchAvailableDoctors();
      this.setData({ availableDoctors: data.doctors || [] });
    } catch (err) {
      console.error('加载医生列表失败', err);
    }
  },

  closeConsultPanel() {
    this.setData({ showConsultPanel: false });
  },

  async sendConsultInvite(e) {
    const { doctorid, doctorname } = e.currentTarget.dataset;
    this.setData({ showConsultPanel: false });
    wx.showLoading({ title: '发送邀请...', mask: true });
    try {
      await chatApi.inviteConsult({
        assignment_id: this.data.assignmentId,
        target_doctor_id: doctorid,
        note: '需要您协助会诊',
      });
      wx.hideLoading();
      wx.showToast({ title: '邀请已发送', icon: 'success' });
      await this.loadMessages();
    } catch (err) {
      wx.hideLoading();
      wx.showToast({ title: err.message || '邀请失败', icon: 'none' });
    }
  },

  // 处理系统消息（会诊邀请接受/拒绝）
  async handleConsult(e) {
    const { messageid, action } = e.currentTarget.dataset;
    try {
      await chatApi.respondConsult({
        message_id: messageid,
        accept: action === 'accept',
      });
      wx.showToast({ title: action === 'accept' ? '已加入会诊' : '已婉拒', icon: 'success' });
      await this.loadMessages();
    } catch (err) {
      wx.showToast({ title: err.message || '操作失败', icon: 'none' });
    }
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
    wx.previewImage({ urls: [url], current: url });
  },
});
