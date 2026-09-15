const navigation = require('../../utils/navigation.js');
// pages/checkin/checkin.js
// 打卡指导区 - 千问 AI 建议（文字版）
const checkinState = require('../../utils/checkin-state.js');
const plainSuggestion = text => String(text || '').replace(/\*\*(.*?)\*\*/g, '$1').replace(/^#{1,6}\s+/gm, '').replace(/`([^`]+)`/g, '$1');
const { generateDailySuggestions } = require('../../utils/qwen_chat.js');

Page({
  data: {
    todayCheckin: {
      diet: false,
      exercise: false,
      water: false
    },
    stats: {
      totalDays: 0,
      continueDays: 0,
      calories: 0
    },
    recentRecords: [],
    positiveFeedback: {
      doneCount: 0, percent: 0, weekDays: 0, weekTrail: [],
      title: '今天，从一小步开始',
      message: '从膳食、运动、饮水中选一项，完成后点一下记录。',
      lastAction: ''
    },
    aiSuggestions: [],  // AI 建议
    aiSuggestionText: '',  // 单条 AI 建议
    loadingAI: false,
    aiSuggestionError: '',
    wechatSteps: 0,
    targetSteps: 10000,
    userInfo: null,
    today: ''
  },

  onLoad() {
    const now = new Date();
    this.setData({
      today: `${now.getMonth() + 1}月${now.getDate()}日 ${['周日','周一','周二','周三','周四','周五','周六'][now.getDay()]}`
    });
    this.loadWechatSteps();
  },

  onShow() {
    this.loadUserInfo();
    this.loadTodayData();
    this.loadRecentRecords();
    this.loadAISuggestions();
  },

  loadUserInfo() {
    const userInfo = wx.getStorageSync('userInfo') || wx.getStorageSync('profile') || null;
    this.setData({ userInfo });
  },

  loadTodayData(lastAction = '') {
    const records = wx.getStorageSync(checkinState.storageKey()) || [];
    const now = new Date();
    this.setData({
      ...checkinState.summarize(records, now),
      positiveFeedback: checkinState.positiveFeedback(records, now, lastAction),
      today: `${now.getMonth()+1}月${now.getDate()}日`
    });
  },
  loadRecentRecords() {
    this.setData({ recentRecords: (wx.getStorageSync(checkinState.storageKey()) || []).slice(0, 5) });
  },

  // 加载 AI 建议
  refreshAISuggestions() {
    return this.loadAISuggestions(true);
  },

  loadAISuggestions(force = false) {
    if (this.data.loadingAI) return;
    const { todayCheckin, userInfo } = this.data;

    // 从缓存获取今日建议
    const todayKey = `ai_suggestions_${checkinState.storageKey()}_${checkinState.dayKey()}`;
    const cached = wx.getStorageSync(todayKey);

    if (cached && force !== true) {
      this.setData({ aiSuggestionText: plainSuggestion(cached) });
      return;
    }

    this.setData({ loadingAI: true, aiSuggestionError: '' });

    // 调用千问 AI 生成建议
    const profile = {
      age: userInfo?.age || '',
      sex: userInfo?.sex || '',
      heightCm: userInfo?.heightCm || '',
      weightKg: userInfo?.weightKg || '',
      bmi: userInfo?.bmi || ''
    };

    return generateDailySuggestions(todayCheckin, profile)
      .then(suggestion => {
        if (todayKey !== `ai_suggestions_${checkinState.storageKey()}_${checkinState.dayKey()}`) return;
        this.setData({
          aiSuggestionText: plainSuggestion(suggestion),
          loadingAI: false
        });
        wx.setStorageSync(todayKey, suggestion);
        if (force === true) wx.showToast({ title: '建议已更新', icon: 'success' });
      })
      .catch(err => {
        console.error('AI 建议生成失败:', err);
        if (todayKey !== `ai_suggestions_${checkinState.storageKey()}_${checkinState.dayKey()}`) return;
        // 刷新失败时保留已有建议，并明确告知用户。
        const defaultSuggestion = this.getDefaultSuggestion(todayCheckin);
        this.setData({
          aiSuggestionText: this.data.aiSuggestionText || plainSuggestion(cached) || defaultSuggestion,
          aiSuggestionError: '暂时无法更新建议，请稍后重试',
          loadingAI: false
        });
      }).finally(() => this.setData({ loadingAI: false }));
  },

  // 默认建议（AI 不可用时）
  getDefaultSuggestion(todayCheckin) {
    let suggestion = '今日健康建议：\n\n';

    if (!todayCheckin.diet) {
      suggestion += '膳食：记得按时吃三餐，多摄入蔬菜水果（每天至少500g）\n\n';
    }
    if (!todayCheckin.exercise) {
      suggestion += '运动：建议进行30分钟有氧运动，如快走、慢跑\n\n';
    }
    if (!todayCheckin.water) {
      suggestion += '饮水：多喝水，每天1500-2000ml，少量多次饮用\n\n';
    }

    suggestion += '坚持每日打卡，养成健康习惯！';
    return suggestion;
  },

  loadWechatSteps() {
    // 未接入后端解密之前不展示模拟步数。
    this.setData({ wechatSteps: 0 });
  },

  doCheckin(e) {
    const { type } = e.currentTarget.dataset;
    if (!['diet','exercise','water'].includes(type)) return;
    this.loadTodayData();
    if (this.data.todayCheckin[type]) { wx.showToast({ title: '今日已打卡', icon: 'none' }); return; }
    const records = wx.getStorageSync(checkinState.storageKey()) || [];
    records.unshift({ id: Date.now(), type,
      typeText: {diet: '膳食打卡', exercise: '运动打卡', water: '饮水打卡'}[type],
      day: checkinState.dayKey(), date: checkinState.dayKey(), time: new Date().toLocaleTimeString() });
    wx.setStorageSync(checkinState.storageKey(), records);
    this.loadTodayData(`${records[0].typeText}已记录`);
    this.loadRecentRecords();
    wx.showToast({ title: this.data.positiveFeedback.doneCount === 3 ? '今日三项完成' : '打卡已记录', icon: 'success' });
    wx.vibrateShort({ type: 'light' });
  },

  viewRecords() {
    navigation.open({
      url: '/pages/checkin-record/checkin-record'
    });
  },


});
