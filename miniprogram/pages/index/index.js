// pages/index/index.js
const { request } = require('../../utils/request.js');

Page({
  data: {
    greeting: '早上好',
    quickEntries: [
      { icon: '📷', label: '拍照识膳食', path: '/pages/capture/capture' },
      { icon: '📚', label: '营养知识', path: '/pages/knowledge/knowledge' },
      { icon: '🗺️', label: '毒蘑菇地图', path: '/pages/gis-map/gis-map' },
      { icon: '👤', label: '健康档案', path: '/pages/profile/profile' }
    ],
    todayCalories: 0,
    todayTarget: 2000
  },

  onShow() {
    this.setData({ greeting: this.computeGreeting() });
    this.loadTodaySummary();
  },

  computeGreeting() {
    const h = new Date().getHours();
    if (h < 6) return '夜深了，注意休息';
    if (h < 11) return '早上好';
    if (h < 14) return '中午好';
    if (h < 18) return '下午好';
    return '晚上好';
  },

  loadTodaySummary() {
    request({ url: '/reports/today', showLoading: false })
      .then((data) => {
        this.setData({
          todayCalories: data.calories || 0,
          todayTarget: data.target || 2000
        });
      })
      .catch(() => {});
  },

  goTo(e) {
    const { path } = e.currentTarget.dataset;
    if (!path) return;
    if (path.startsWith('/pages/')) {
      wx.navigateTo({ url: path });
    }
  }
});