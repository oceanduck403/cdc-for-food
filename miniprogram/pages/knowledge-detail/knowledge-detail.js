// pages/knowledge-detail/knowledge-detail.js
const { request } = require('../../utils/request.js');

Page({
  data: { id: '', article: null, loading: true },

  onLoad(options) {
    this.setData({ id: options.id || '' }, this.load);
  },

  load() {
    request({ url: `/knowledge/${this.data.id}`, showLoading: false })
      .then((data) => this.setData({ article: data, loading: false }))
      .catch(() => this.setData({ loading: false }));
  }
});