const community = require('../../utils/community.js');
const navigation = require('../../utils/navigation.js');

Page({
  data: { loggedIn:false, items:[], loading:false, error:'', hasMore:false, nextCursor:0, busy:{} },

  onShow() {
    const loggedIn = community.loggedIn();
    this.setData({loggedIn});
    if (loggedIn) this.refresh();
  },

  onPullDownRefresh() { this.refresh().finally(() => wx.stopPullDownRefresh()); },
  onReachBottom() { this.loadMore(); },

  async refresh() {
    if (!community.loggedIn()) return;
    const loadId = this._loadId = (this._loadId || 0) + 1;
    this.setData({items:[], loading:true, error:'', hasMore:false, nextCursor:0});
    try {
      const data = await community.favorites(0);
      if (loadId !== this._loadId) return;
      this.setData({items:(data.items || []).map(community.formatArticle), hasMore:!!data.hasMore,
        nextCursor:data.nextCursor || 0});
    } catch (err) {
      if (loadId === this._loadId) this.setData({error:err.message || '收藏加载失败，请重试'});
    } finally {
      if (loadId === this._loadId) this.setData({loading:false});
    }
  },

  async loadMore() {
    if (!this.data.hasMore || this.data.loading) return;
    const loadId = this._loadId;
    this.setData({loading:true});
    try {
      const data = await community.favorites(this.data.nextCursor);
      if (loadId !== this._loadId) return;
      this.setData({items:[...this.data.items, ...(data.items || []).map(community.formatArticle)],
        hasMore:!!data.hasMore, nextCursor:data.nextCursor || 0});
    } catch (err) {
      if (loadId === this._loadId) wx.showToast({title:err.message || '加载失败，请重试', icon:'none'});
    } finally {
      if (loadId === this._loadId) this.setData({loading:false});
    }
  },

  openArticle(e) { navigation.open(`/pages/knowledge-detail/knowledge-detail?id=${e.currentTarget.dataset.id}`); },
  goScience() { navigation.open('/pages/science/science'); },
  goLogin() { community.requireLogin(); },

  async removeFavorite(e) {
    const id = e.currentTarget.dataset.id;
    if (this.data.busy[id]) return;
    this.setData({busy:{...this.data.busy, [id]:true}});
    try {
      await community.react(id, 'favorite', false);
      this.setData({items:this.data.items.filter(item => String(item.id) !== String(id))});
      wx.showToast({title:'已取消收藏', icon:'none'});
      if (this.data.hasMore && this.data.items.length < 5) this.refresh();
    } catch (err) {
      wx.showToast({title:err.message || '操作失败，请重试', icon:'none'});
    } finally {
      this.setData({busy:{...this.data.busy, [id]:false}});
    }
  }
});
