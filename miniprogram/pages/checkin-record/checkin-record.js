// pages/checkin-record/checkin-record.js
// 打卡记录页面
const checkinState = require('../../utils/checkin-state.js');

Page({
  data: {
    records: [],
    loading: true,
    currentMonth: '',
    monthStats: {
      total: 0,
      diet: 0,
      exercise: 0,
      water: 0
    }
  },

  onLoad() {
    const now = new Date();
    this.setData({
      currentMonth: `${now.getFullYear()}年${now.getMonth() + 1}月`
    });
    this.loadRecords();
  },

  // 加载打卡记录
  loadRecords() {
    this.setData({ records: wx.getStorageSync(checkinState.storageKey()) || [], loading: false });
    this.calcMonthStats();
  },

  // 计算月度统计
  calcMonthStats() {
    const { records } = this.data;
    const now = new Date();
    const currentMonth = now.getMonth();
    const currentYear = now.getFullYear();

    const monthRecords = records.filter(r => {
      const date = new Date(r.date);
      return date.getMonth() === currentMonth && date.getFullYear() === currentYear;
    });

    const stats = {
      total: monthRecords.length,
      diet: monthRecords.filter(r => r.type === 'diet').length,
      exercise: monthRecords.filter(r => r.type === 'exercise').length,
      water: monthRecords.filter(r => r.type === 'water').length
    };

    this.setData({ monthStats: stats });
  },

  // 删除记录
  deleteRecord(e) {
    const { id } = e.currentTarget.dataset;
    wx.showModal({
      title: '删除记录',
      content: '确定要删除这条打卡记录吗？',
      success: (res) => {
        if (res.confirm) {
          const records = this.data.records.filter(r => r.id !== id);
          this.setData({ records });
          wx.setStorageSync(checkinState.storageKey(), records);
          this.calcMonthStats();
          wx.showToast({ title: '已删除', icon: 'success' });
        }
      }
    });
  }
});
