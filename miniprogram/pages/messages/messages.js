const community = require('../../utils/community.js');
const navigation = require('../../utils/navigation.js');

const FILTERS = [
  {id:'all', label:'全部'}, {id:'received', label:'回复我的'},
  {id:'like', label:'点赞'}, {id:'comment', label:'评论'}, {id:'favorite', label:'收藏'}
];
const ICONS = {like:'like', comment_like:'like', comment:'comment', reply:'comment', favorite:'star'};

function present(message) {
  const who = message.self ? '你' : message.actor;
  const descriptions = {
    like: `${who}点赞了文章`,
    favorite: `${who}收藏了文章`,
    comment: `${who}发表了评论`,
    reply: `${who}回复了你的评论`,
    comment_like: `${who}点赞了你的评论`
  };
  return {
    ...message,
    icon: ICONS[message.kind] || 'bell',
    description: descriptions[message.kind] || `${who}有新的互动`,
    date: community.dateLabel(message.createdAt)
  };
}

Page({
  data: {
    filters: FILTERS, filter: 'all', items: [], loading: false,
    error: '', hasMore: false, nextCursor: 0, unreadCount: 0, loggedIn: false,
    markingAll: false
  },

  onShow() {
    const loggedIn = community.loggedIn();
    this.setData({loggedIn});
    if (loggedIn) this.refresh();
  },

  onPullDownRefresh() {
    this.refresh().finally(() => wx.stopPullDownRefresh());
  },

  onReachBottom() { this.loadMore(); },

  async refresh() {
    if (!community.loggedIn()) return;
    const loadId = this._loadId = (this._loadId || 0) + 1;
    this.setData({loading:true, error:'', items:[], hasMore:false, nextCursor:0});
    try {
      const [data, unread] = await Promise.all([community.messages(this.data.filter, 0), community.unread()]);
      if (loadId !== this._loadId) return;
      this.setData({items:(data.items || []).map(present), hasMore:!!data.hasMore,
        nextCursor:data.nextCursor || 0, unreadCount:unread.count || 0});
    } catch (err) {
      if (loadId === this._loadId) this.setData({error:err.message || '消息加载失败，请重试'});
    } finally {
      if (loadId === this._loadId) this.setData({loading:false});
    }
  },

  selectFilter(e) {
    const filter = e.currentTarget.dataset.filter;
    if (filter === this.data.filter) return;
    this.setData({filter}, () => this.refresh());
  },

  async loadMore() {
    if (!this.data.hasMore || this.data.loading) return;
    const loadId = this._loadId;
    this.setData({loading:true});
    try {
      const data = await community.messages(this.data.filter, this.data.nextCursor);
      if (loadId !== this._loadId) return;
      this.setData({items:[...this.data.items, ...(data.items || []).map(present)],
        hasMore:!!data.hasMore, nextCursor:data.nextCursor || 0});
    } catch (err) {
      if (loadId === this._loadId) wx.showToast({title:err.message || '加载失败，请重试', icon:'none'});
    } finally {
      if (loadId === this._loadId) this.setData({loading:false});
    }
  },

  async markAllRead() {
    if (!this.data.unreadCount || this.data.markingAll) return;
    this.setData({markingAll:true});
    try {
      await community.readAll();
      this.setData({items:this.data.items.map(item => ({...item, read:true})), unreadCount:0});
      wx.showToast({title:'已全部标为已读', icon:'none'});
    } catch (err) {
      wx.showToast({title:err.message || '操作失败，请重试', icon:'none'});
    } finally {
      this.setData({markingAll:false});
    }
  },

  async openMessage(e) {
    const id = Number(e.currentTarget.dataset.id);
    const message = this.data.items.find(item => item.id === id);
    if (!message) return;
    if (!message.read) {
      try {
        await community.read(id);
        this.setData({items:this.data.items.map(item => item.id === id ? {...item, read:true} : item),
          unreadCount:Math.max(0,this.data.unreadCount-1)});
      } catch (err) { wx.showToast({title:err.message || '标记已读失败', icon:'none'}); }
    }
    navigation.open(`/pages/knowledge-detail/knowledge-detail?id=${message.articleId}`);
  },

  goLogin() { community.requireLogin(); }
});
