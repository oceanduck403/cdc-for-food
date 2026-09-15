// pages/report/report.js
const { request } = require('../../utils/request.js');

Page({
  data: {
    mealId: '',
    report: null,
    loading: true
  },

  onLoad(options) {
    this.setData({ mealId: options.id || '' }, this.load);
  },

  load() {
    this.setData({ loading: true });
    const url = `/meals/${this.data.mealId || 'latest'}/report`;
    request({ url, showLoading: false })
      .then((data) => this.setData({ report: data || null, loading: false }))
      .catch(() => {
        this.setData({ report: null, loading: false });
        wx.showToast({ title: '报告加载失败，请稍后重试', icon: 'none' });
      });
  }
});
