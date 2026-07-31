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
    request({ url: `/meals/${this.data.mealId || 'latest'}/report`, showLoading: false })
      .then((data) => this.setData({ report: data, loading: false }))
      .catch(() => this.setData({ loading: false }));
  }
});