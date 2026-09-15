// pages/science-detail/science-detail.js
// 科普文章详情页面
const { request } = require('../../utils/request.js');

Page({
  data: {
    article: null,
    loading: true
  },

  onLoad(options) {
    if (options.id) {
      this.loadArticle(options.id);
    }
  },

  loadArticle(id) {
    this.setData({ loading: true });

    request({ url: `/knowledge/${id}`, showLoading: true })
      .then(data => {
        this.setData({
          article: data,
          loading: false
        });
      })
      .catch(() => {
        // 使用本地缓存
        const articles = wx.getStorageSync('knowledge_articles') || [];
        const article = articles.find(a => a.id === id);
        this.setData({
          article: article || { title: '文章不存在', content: '该文章可能已被删除或移动。' },
          loading: false
        });
      });
  }
});
