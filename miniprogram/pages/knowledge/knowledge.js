// pages/knowledge/knowledge.js
const { request } = require('../../utils/request.js');
const config = require('../../utils/config.js');

const CATEGORIES = [
  { id: 'guide',   name: '膳食指南',    icon: '🥗' },
  { id: 'mushroom',name: '毒蘑菇',      icon: '🍄' },
  { id: 'safety',  name: '食品安全',    icon: '🔬' },
  { id: 'disease', name: '食源性疾病',  icon: '🦠' },
  { id: 'vaccine', name: '疫苗科普',    icon: '💉' },
];

// 分类 → 标签色
const TAG_COLORS = {
  guide:    { bg: '#E8F5F0', text: '#0F8A65' },
  mushroom: { bg: '#FEE2E2', text: '#EF4444' },
  safety:   { bg: '#FEF3C7', text: '#B45309' },
  disease:  { bg: '#EDE9FE', text: '#7C3AED' },
  vaccine:  { bg: '#DBEAFE', text: '#2563EB' },
};

Page({
  data: {
    categories: CATEGORIES,
    active: 'guide',
    list: [],
    loading: true,
    keyword: ''
  },

  onShow() {
    this.load();
  },

  switchCategory(e) {
    this.setData({ active: e.currentTarget.dataset.id, keyword: '' }, this.load);
  },

  onSearch(e) {
    this.setData({ keyword: e.detail.value }, this.load);
  },

  clearSearch() {
    this.setData({ keyword: '' }, this.load);
  },

  // 加载知识库数据
  load() {
    this.setData({ loading: true });

    // 外部知识库模式
    if (config.knowledgeBase && config.knowledgeBase.enabled) {
      this.loadFromExternal();
      return;
    }

    // Mock 模式
    const q = encodeURIComponent(this.data.keyword || '');
    const url = `/knowledge?category=${this.data.active}&q=${q}`;
    request({ url, showLoading: false })
      .then((data) => {
        const items = (data && data.items) || [];
        const colored = items.map(item => ({
          ...item,
          tagColor: TAG_COLORS[this.data.active]?.bg || '#E8F5F0',
        }));
        this.setData({ list: colored, loading: false });
      })
      .catch(() => this.setData({ loading: false }));
  },

  // 从 GitHub 外部知识库加载
  loadFromExternal() {
    const category = this.data.active;
    const keyword = this.data.keyword || '';

    wx.request({
      url: `${config.knowledgeBase.baseUrl}/knowledge-index.json`,
      method: 'GET',
      success: (res) => {
        if (res.statusCode === 200 && res.data) {
          const catData = res.data[category];
          let items = catData && catData.items ? catData.items : [];

          // 搜索过滤
          if (keyword) {
            const kw = keyword.toLowerCase();
            items = items.filter(item =>
              item.title.toLowerCase().includes(kw) ||
              item.summary.toLowerCase().includes(kw)
            );
          }

          // 添加标签颜色
          items = items.map(item => ({
            ...item,
            tagColor: TAG_COLORS[category]?.bg || '#E8F5F0',
          }));

          this.setData({ list: items, loading: false });
        } else {
          this.setData({ loading: false });
        }
      },
      fail: () => {
        this.setData({ loading: false });
        wx.showToast({ title: '加载失败，请稍后重试', icon: 'none' });
      }
    });
  },

  openArticle(e) {
    const { id } = e.currentTarget.dataset;
    if (!id) return;

    // 外部知识库模式：跳转原文链接
    if (config.knowledgeBase && config.knowledgeBase.enabled) {
      this.getArticleAndShow(id);
      return;
    }

    wx.navigateTo({ url: `/pages/knowledge-detail/knowledge-detail?id=${id}` });
  },

  // 获取文章详情并展示
  getArticleAndShow(id) {
    wx.showLoading({ title: '加载中...' });

    wx.request({
      url: `${config.knowledgeBase.baseUrl}/knowledge.json`,
      method: 'GET',
      success: (res) => {
        wx.hideLoading();
        if (res.statusCode === 200 && res.data && res.data.items) {
          const article = res.data.items.find(item => item.id === id);
          if (article) {
            // 显示文章详情弹窗
            wx.showModal({
              title: article.title,
              content: article.summary + '\n\n来源：' + article.source,
              confirmText: '阅读原文',
              cancelText: '关闭',
              success: (modalRes) => {
                if (modalRes.confirm && article.originalUrl) {
                  // 复制链接
                  wx.setClipboardData({
                    data: article.originalUrl,
                    success: () => {
                      wx.showToast({ title: '链接已复制，请在浏览器打开', icon: 'none' });
                    }
                  });
                }
              }
            });
          }
        }
      },
      fail: () => {
        wx.hideLoading();
        wx.showToast({ title: '加载失败', icon: 'none' });
      }
    });
  }
});
