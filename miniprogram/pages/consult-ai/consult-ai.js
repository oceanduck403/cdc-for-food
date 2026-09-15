const { chatWithHistory } = require('../../utils/qwen_chat.js');
const { analyzeFoodFromImage } = require('../../utils/qwen.js');
const { dayKey } = require('../../utils/checkin-state.js');

const quickPrompts = [
  { id: 'diet', label: '一日三餐', prompt: '我想吃得更均衡，一日三餐应该怎样搭配？', icon: 'leaf' },
  { id: 'exercise', label: '适量运动', prompt: '我平时运动少，怎样安全地开始锻炼？', icon: 'activity' },
  { id: 'weight', label: '体重管理', prompt: '我想管理体重，应该先从哪些生活习惯开始？', icon: 'chart' },
  { id: 'safety', label: '食品安全', prompt: '如何在日常生活中注意食品安全？', icon: 'check' },
];

Page({
  data: {
    messages: [], userInput: '', sending: false, usedTimes: 0, freeTimes: 10,
    showNoTimesModal: false, scrollIntoView: '', error: '', quickPrompts,
  },
  onLoad() { this.restore(); },
  onShow() { this.restore(); },
  identity() {
    const profile = wx.getStorageSync('profile') || {};
    return String(profile.id || 'guest');
  },
  restore() {
    const identity = this.identity();
    const token = wx.getStorageSync('token') || '';
    if (this._identity !== identity || this._token !== token) this.setData({ userInput: '', error: '' });
    this._identity = identity;
    this._token = token;
    this._key = `floating_ai_${identity}`;
    this._quotaKey = `${this._key}_quota_${dayKey()}`;
    const saved = wx.getStorageSync(this._key);
    const messages = Array.isArray(saved) ? saved.slice(-30) : [];
    this.setData({ messages, usedTimes: Number(wx.getStorageSync(this._quotaKey)) || 0,
      scrollIntoView: messages.length ? messages[messages.length - 1].id : '' });
  },
  onInputChange(e) { this.setData({ userInput: e.detail.value }); },
  clickTemplate(e) {
    if (this.data.sending) return;
    const item = quickPrompts.find(prompt => prompt.id === e.currentTarget.dataset.id);
    if (!item) return;
    this.setData({ userInput: item.prompt });
    this.sendMessage();
  },
  async sendMessage() {
    const text = String(this.data.userInput || '').trim();
    if (!text || this.data.sending) return;
    if (this.data.usedTimes >= this.data.freeTimes) { this.setData({ showNoTimesModal: true }); return; }
    if (this.identity() !== this._identity || (wx.getStorageSync('token') || '') !== this._token) { this.restore(); return; }
    const key = this._key;
    const token = this._token;
    const before = this.data.messages;
    const id = `ai-${Date.now()}`;
    this.setData({ sending: true, userInput: '', error: '',
      messages: [...before, { id, role: 'user', content: text, time_str: this.formatTime(new Date()) }], scrollIntoView: id });
    try {
      const history = before.slice(-12).filter(message => message.role === 'user' || message.role === 'assistant')
        .map(message => ({ role: message.role, content: message.content }));
      const answer = await chatWithHistory(text, history);
      const reply = answer && typeof answer.reply === 'string' ? answer.reply.trim() : '';
      if (!reply) throw new Error('回复为空');
      if (this.identity() !== this._identity || this._key !== key || (wx.getStorageSync('token') || '') !== token) return;
      const replyId = `${id}-reply`;
      const messages = [...before, { id, role: 'user', content: text, time_str: this.formatTime(new Date()) },
        { id: replyId, role: 'assistant', content: reply, time_str: this.formatTime(new Date()) }].slice(-30);
      const usedTimes = this.data.usedTimes + 1;
      wx.setStorageSync(key, messages);
      wx.setStorageSync(this._quotaKey, usedTimes);
      this.setData({ messages, usedTimes, scrollIntoView: replyId });
    } catch (err) {
      if (this._key === key) this.setData({ messages: before, userInput: text, error: '暂时无法获取回复，请检查网络后重试。' });
    } finally {
      if (this._key === key) this.setData({ sending: false });
    }
  },
  chooseImage() {
    if (this.data.sending) return;
    if (this.data.usedTimes >= this.data.freeTimes) { this.setData({ showNoTimesModal: true }); return; }
    wx.chooseMedia({ count: 1, mediaType: ['image'], sourceType: ['album', 'camera'],
      success: res => { const item = res.tempFiles && res.tempFiles[0]; if (item) this.analyzeImage(item.tempFilePath); },
      fail: err => { if (!/cancel/i.test(err.errMsg || '')) wx.showToast({ title: '选择图片失败，请重试', icon: 'none' }); },
    });
  },
  async analyzeImage(filePath) {
    if (this.data.sending) return;
    const key = this._key;
    const before = this.data.messages;
    const id = `food-${Date.now()}`;
    this.setData({ sending: true, error: '', messages: [...before,
      { id, role: 'user', content: '请帮我看看这张食物照片', image: filePath, time_str: this.formatTime(new Date()) }], scrollIntoView: id });
    try {
      const result = await analyzeFoodFromImage(filePath);
      const reply = result && result.description ? result.description : '暂未识别出食物，请换一张清晰照片。';
      if (this._key !== key) return;
      const replyId = `${id}-reply`;
      const messages = [...before, { id, role: 'user', content: '已提交一张食物照片', time_str: this.formatTime(new Date()) },
        { id: replyId, role: 'assistant', content: reply, time_str: this.formatTime(new Date()) }].slice(-30);
      const usedTimes = this.data.usedTimes + 1;
      wx.setStorageSync(key, messages);
      wx.setStorageSync(this._quotaKey, usedTimes);
      this.setData({ messages, usedTimes, scrollIntoView: replyId });
    } catch (err) {
      if (this._key === key) this.setData({ messages: before, error: '图片识别暂时失败，请换张清晰照片重试。' });
    } finally { if (this._key === key) this.setData({ sending: false }); }
  },
  previewImage(e) {
    const url = e.currentTarget.dataset.url;
    if (url) wx.previewImage({ urls: [url], current: url });
  },
  closeNoTimesModal() { this.setData({ showNoTimesModal: false }); },
  noop() {},
  formatTime(date) {
    return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;
  },
  clearMessages() {
    wx.showModal({ title: '清空对话记录？', content: '清空后无法恢复，今日已用次数不会重置。',
      success: res => { if (res.confirm) { wx.setStorageSync(this._key, []); this.setData({ messages: [], scrollIntoView: '' }); } },
    });
  },
});
