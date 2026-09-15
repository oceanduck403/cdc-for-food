const community = require('../../utils/community.js');

function formatComment(comment) {
  return { ...comment, date: community.dateLabel(comment.createdAt) };
}
const CATEGORY_NAMES = {guide:'膳食指南', mushroom:'毒蘑菇', safety:'食品安全', disease:'食源性疾病', vaccine:'疫苗科普', nutrition:'营养知识'};

Page({
  data: {
    id: '', article: null, loading: true, error: '', actionBusy: false,
    comments: [], commentsLoading: false, commentsError: '', hasMore: false, nextCursor: 0,
    commentText: '', replyId: null, replyAuthor: '', submitting: false,
    commentBusy: {}
  },

  onLoad(options) {
    this.setData({ id: options.id || '' });
  },

  onShow() {
    if (this.data.id) this.refresh();
  },

  onPullDownRefresh() {
    this.refresh().finally(() => wx.stopPullDownRefresh());
  },

  async refresh() {
    this.setData({ loading: true, error: '' });
    const result = await Promise.all([this.loadArticle(), this.loadComments(true)]);
    this.setData({ loading: false });
    return result;
  },

  async loadArticle() {
    try {
      const article = await community.article(this.data.id);
      this.setData({ article: { ...community.formatArticle(article), categoryName: CATEGORY_NAMES[article.category] || '健康知识' }, error: '' });
    } catch (err) {
      this.setData({ error: err.message || '文章加载失败，请稍后重试' });
    }
  },

  async loadComments(reset) {
    if (this.data.commentsLoading) return;
    this.setData({ commentsLoading: true, commentsError: '' });
    try {
      const data = await community.comments(this.data.id, reset ? 0 : this.data.nextCursor);
      const incoming = (data.items || []).map(formatComment);
      this.setData({
        comments: reset ? incoming : [...this.data.comments, ...incoming],
        hasMore: !!data.hasMore,
        nextCursor: data.nextCursor || 0
      });
    } catch (err) {
      this.setData({ commentsError: err.message || '评论加载失败，请重试' });
    } finally {
      this.setData({ commentsLoading: false });
    }
  },

  loadMoreComments() {
    if (this.data.hasMore) this.loadComments(false);
  },

  retryComments() { this.loadComments(this.data.comments.length === 0); },

  async toggleArticleReaction(e) {
    const kind = e.currentTarget.dataset.kind;
    const article = this.data.article;
    if (!article || this.data.actionBusy || !community.requireLogin()) return;
    const active = !article[kind === 'like' ? 'liked' : 'favorited'];
    this.setData({ actionBusy: true });
    try {
      this.setData({ article: { ...this.data.article, ...community.formatArticle(await community.react(this.data.id, kind, active)) } });
      wx.showToast({ title: kind === 'like' ? (active ? '已点赞' : '已取消点赞') : (active ? '已收藏' : '已取消收藏'), icon: 'none' });
    } catch (err) {
      wx.showToast({ title: err.message || '操作失败，请重试', icon: 'none' });
    } finally {
      this.setData({ actionBusy: false });
    }
  },

  onCommentInput(e) {
    const value = e.detail.value;
    if (value !== this.data.commentText) this._pendingSubmitId = null;
    this.setData({ commentText: value });
  },

  replyComment(e) {
    if (!community.requireLogin()) return;
    this._pendingSubmitId = null;
    this.setData({ replyId: e.currentTarget.dataset.id, replyAuthor: e.currentTarget.dataset.author, commentText: '' });
  },

  cancelReply() {
    this._pendingSubmitId = null;
    this.setData({ replyId: null, replyAuthor: '', commentText: '' });
  },

  async submitComment() {
    if (this.data.submitting || !community.requireLogin()) return;
    const content = this.data.commentText.trim();
    if (!content) { wx.showToast({ title: '请先输入评论', icon: 'none' }); return; }
    const requestId = this._pendingSubmitId || `${Date.now()}_${Math.random().toString(36).slice(2, 12)}`;
    this._pendingSubmitId = requestId;
    this.setData({ submitting: true });
    try {
      await community.comment(this.data.id, { content, parent_id: this.data.replyId || null, request_id: requestId });
      this._pendingSubmitId = null;
      this.setData({ commentText: '', replyId: null, replyAuthor: '' });
      await Promise.all([this.loadArticle(), this.loadComments(true)]);
      wx.showToast({ title: '评论已发布', icon: 'none' });
    } catch (err) {
      wx.showToast({ title: err.message || '发布失败，请重试', icon: 'none' });
    } finally {
      this.setData({ submitting: false });
    }
  },

  async toggleCommentLike(e) {
    if (!community.requireLogin()) return;
    const id = Number(e.currentTarget.dataset.id);
    if (this.data.commentBusy[id]) return;
    const comment = this.data.comments.find(c => c.id === id);
    if (!comment) return;
    this.setData({ commentBusy: { ...this.data.commentBusy, [id]: true } });
    try {
      const state = await community.likeComment(id, !comment.liked);
      this.setData({ comments: this.data.comments.map(c => c.id === id ? { ...c, ...state } : c) });
    } catch (err) {
      wx.showToast({ title: err.message || '操作失败，请重试', icon: 'none' });
    } finally {
      this.setData({ commentBusy: { ...this.data.commentBusy, [id]: false } });
    }
  },

  deleteComment(e) {
    const id = e.currentTarget.dataset.id;
    wx.showModal({
      title: '删除评论', content: '确定删除这条评论吗？',
      success: async (res) => {
        if (!res.confirm) return;
        try {
          await community.deleteComment(id);
          await Promise.all([this.loadArticle(), this.loadComments(true)]);
          wx.showToast({ title: '已删除', icon: 'none' });
        } catch (err) {
          wx.showToast({ title: err.message || '删除失败，请重试', icon: 'none' });
        }
      }
    });
  },

  reportComment(e) {
    if (!community.requireLogin()) return;
    const id = e.currentTarget.dataset.id;
    const reasons = ['垃圾广告', '不实信息', '不友善评论'];
    wx.showActionSheet({
      itemList: reasons,
      success: async (res) => {
        try {
          await community.reportComment(id, reasons[res.tapIndex]);
          wx.showToast({ title: '举报已提交', icon: 'none' });
        } catch (err) {
          wx.showToast({ title: err.message || '提交失败，请重试', icon: 'none' });
        }
      }
    });
  },

  onShareAppMessage() {
    return { title: this.data.article?.title || '健康科普', path: `/pages/knowledge-detail/knowledge-detail?id=${this.data.id}` };
  }
});
