// pages/knowledge/knowledge.js
const { request } = require('../../utils/request.js');

Page({
  data: {
    categories: [
      { id: 'guide', name: '膳食指南' },
      { id: 'mushroom', name: '毒蘑菇' },
      { id: 'safety', name: '食品安全' },
      { id: 'disease', name: '食源性疾病' }
    ],
    active: 'guide',
    list: [],
    loading: true,
    keyword: ''
  },

  onShow() {
    this.load();
  },

  switchCategory(e) {
    this.setData({ active: e.currentTarget.dataset.id }, this.load);
  },

  onSearch(e) {
    this.setData({ keyword: e.detail.value }, this.load);
  },

  load() {
    this.setData({ loading: true });
    const params = new URLSearchParams({
      category: this.data.active,
      q: this.data.keyword
    }).toString();
    request({ url: `/knowledge?${params}`, showLoading: false })
      .then((data) => this.setData({ list: data.items || [], loading: false }))
      .catch(() => this.setData({ loading: false }));
  },

  openArticle(e) {
    const { id } = e.currentTarget.dataset;
    wx.navigateTo({ url: `/pages/knowledge-detail/knowledge-detail?id=${id}` });
  }
});