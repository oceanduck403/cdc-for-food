// pages/knowledge-detail/knowledge-detail.js
const { request } = require('../../utils/request.js');
const mock = require('../../utils/mock.js');

Page({
  data: { id: '', article: null, loading: true },

  onLoad(options) {
    this.setData({ id: options.id || '' }, this.load);
  },

  load() {
    request({ url: `/knowledge/${this.data.id}`, showLoading: false })
      .then((data) => this.setData({
        article: data || mock.knowledgeArticles[this.data.id] || {
          title: '示例文章',
          source: '演示数据',
          updatedAt: '2026-07-30',
          contentHtml: '<p style="line-height:1.7">这是演示内容，请接入真实知识库。</p>'
        },
        loading: false
      }))
      .catch(() => this.setData({ loading: false }));
  }
});
