// pages/report/report.js
const { request } = require('../../utils/request.js');
const mock = require('../../utils/mock.js');

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
      .then((data) => this.setData({ report: data || mock.mealReport, loading: false }))
      .catch(() => this.setData({ report: mock.mealReport, loading: false }));
  }
});
