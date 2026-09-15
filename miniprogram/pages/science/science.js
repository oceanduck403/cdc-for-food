const navigation = require('../../utils/navigation.js');
// pages/science/science.js
// 科普互动区：健康知识浏览与互动，后续对接疾控中心素材
const community = require('../../utils/community.js');

const CATEGORIES = [
  { id: 'all', name: '全部', color: '#1769A6' },
  { id: 'guide',   name: '膳食指南', color: '#1769A6' },
  { id: 'mushroom',name: '毒蘑菇', color: '#1769A6' },
  { id: 'safety',  name: '食品安全', color: '#1769A6' },
  { id: 'disease', name: '食源性疾病', color: '#1769A6' },
  { id: 'vaccine', name: '疫苗科普', color: '#1769A6' },
  { id: 'nutrition', name: '营养知识', color: '#1769A6' },
];

const TAG_COLORS = {
  guide:    { bg: '#EAF4FB', text: '#1769A6' },
  mushroom: { bg: '#FEE2E2', text: '#EF4444' },
  safety:   { bg: '#FEF3C7', text: '#B45309' },
  disease:  { bg: '#EDE9FE', text: '#7C3AED' },
  vaccine:  { bg: '#DBEAFE', text: '#2563EB' },
  nutrition: { bg: '#EAF4FB', text: '#1769A6' },
};

Page({
  data: {
    categories: CATEGORIES,
    active: 'all',
    list: [],
    loading: true,
    loadError: '',
    loadingMore: false,
    listHasMore: false,
    listNextCursor: 0,
    actionBusy: {},
    keyword: '',
    hotArticles: []
  },

  onShow() {
    this.load();
    this.loadHotArticles();
  },

  onPullDownRefresh() {
    Promise.all([this.load(), this.loadHotArticles()]).finally(() => wx.stopPullDownRefresh());
  },

  // 切换分类
  switchCategory(e) {
    this.setData({ active: e.currentTarget.dataset.id, keyword: '' }, this.load);
  },

  // 搜索
  onSearch(e) {
    this.setData({ keyword: e.detail.value });
    clearTimeout(this._searchTimer);
    this._searchTimer = setTimeout(() => this.load(), 300);
  },

  onUnload() { clearTimeout(this._searchTimer); },

  clearSearch() {
    this.setData({ keyword: '' }, this.load);
  },

  // 加载知识库
  load() {
    const category = this.data.active;
    const keyword = this.data.keyword || '';
    const loadId = this._loadId = (this._loadId || 0) + 1;
    this.setData({ loading: true, loadingMore: false, list: [], loadError: '', listHasMore: false, listNextCursor: 0 });
    return community.articles({category: category === 'all' ? '' : category, q: keyword})
      .then((data) => {
        if (loadId !== this._loadId) return;
        const items = (data && data.items) || [];
        const colored = items.map(item => ({
          ...community.formatArticle(item),
          categoryName: CATEGORIES.find(c => c.id === item.category)?.name || '科普',
          tagColor: TAG_COLORS[item.category]?.bg || '#EAF4FB',
          tagTextColor: TAG_COLORS[item.category]?.text || '#1769A6'
        }));
        this.setData({ list: colored, loading: false, listHasMore: !!data.hasMore, listNextCursor: data.nextCursor || 0 });
      })
      .catch((err) => {
        if (loadId !== this._loadId) return;
        this.setData({ loading: false, loadError: err.message || '加载失败，请重试' });
      });
  },

  onReachBottom() { this.loadMore(); },

  async loadMore() {
    if (!this.data.listHasMore || this.data.loading || this.data.loadingMore) return;
    const loadId = this._loadId;
    this.setData({ loadingMore: true });
    try {
      const data = await community.articles({category:this.data.active === 'all' ? '' : this.data.active, q:this.data.keyword || '', before:this.data.listNextCursor});
      if (loadId !== this._loadId) return;
      const incoming = (data.items || []).map(item => ({
        ...community.formatArticle(item),
        categoryName: CATEGORIES.find(c => c.id === item.category)?.name || '科普',
        tagColor: TAG_COLORS[item.category]?.bg || '#EAF4FB',
        tagTextColor: TAG_COLORS[item.category]?.text || '#1769A6'
      }));
      this.setData({list:[...this.data.list,...incoming], listHasMore:!!data.hasMore, listNextCursor:data.nextCursor || 0});
    } catch (err) {
      wx.showToast({ title: err.message || '加载更多失败', icon: 'none' });
    } finally {
      if (loadId === this._loadId) this.setData({ loadingMore:false });
    }
  },

  // 加载热门文章
  loadHotArticles() {
    return community.articles({limit: 3})
      .then(data => {
        this.setData({ hotArticles: (data.items || []).map(community.formatArticle) });
      })
      .catch(() => this.setData({ hotArticles: [] }));
  },

  // 打开文章
  openArticle(e) {
    const { id } = e.currentTarget.dataset;
    if (!id) return;
    navigation.open({ url: `/pages/knowledge-detail/knowledge-detail?id=${id}` });
  },

  // 点赞文章
  likeArticle(e) {
    return this.toggleReaction(e.currentTarget.dataset.id, 'like');
  },

  favoriteArticle(e) {
    return this.toggleReaction(e.currentTarget.dataset.id, 'favorite');
  },

  async toggleReaction(id, kind) {
    if (!community.requireLogin() || this.data.actionBusy[`${kind}:${id}`]) return;
    const old = this.data.list.find(item => String(item.id) === String(id));
    if (!old) return;
    const busy = { ...this.data.actionBusy, [`${kind}:${id}`]: true };
    this.setData({ actionBusy: busy });
    try {
      const article = await community.react(id, kind, !old[kind === 'like' ? 'liked' : 'favorited']);
      const list = this.data.list.map(item => String(item.id) === String(id) ? { ...item, ...community.formatArticle(article) } : item);
      this.setData({ list });
      wx.showToast({ title: kind === 'like' ? (article.liked ? '已点赞' : '已取消点赞') : (article.favorited ? '已收藏' : '已取消收藏'), icon: 'none' });
    } catch (err) {
      wx.showToast({ title: err.message || '操作失败，请重试', icon: 'none' });
    } finally {
      this.setData({ actionBusy: { ...this.data.actionBusy, [`${kind}:${id}`]: false } });
    }
  },

  // 分享文章
  onShareAppMessage(e) {
    if (e.from === 'button') {
      const { id, title } = e.currentTarget.dataset;
      return {
        title: title || '营养健康知识',
        path: `/pages/knowledge-detail/knowledge-detail?id=${id}`
      };
    }
    return {
      title: '营养健康 AI 小助手',
      path: '/pages/science/science'
    };
  }
});
