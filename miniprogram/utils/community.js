const { request } = require('./api.js');
const navigation = require('./navigation.js');
const base = '/community';
const query = values => Object.keys(values).filter(k => values[k] !== undefined && values[k] !== '').map(k => `${k}=${encodeURIComponent(values[k])}`).join('&');
function loggedIn() { const token = wx.getStorageSync('token'); return !!token && !String(token).startsWith('demo-'); }
function requireLogin() { if (loggedIn()) return true; wx.showToast({ title: '登录后参与互动', icon: 'none' }); navigation.login(); return false; }
function dateLabel(value) { if (!value) return ''; return String(value).replace('T', ' ').slice(0, 16); }
function formatArticle(a) { return { ...a, date: dateLabel(a.updatedAt).slice(0,10) }; }
module.exports = {
  loggedIn, requireLogin, dateLabel, formatArticle,
  articles: params => request(`${base}/articles?${query(params || {})}`),
  article: id => request(`${base}/articles/${id}`),
  react: (id, kind, active) => request({url:`${base}/articles/${id}/reactions/${kind}`,method:'PUT',data:{active}}),
  comments: (id, before=0) => request(`${base}/articles/${id}/comments?before=${before}`),
  comment: (id, data) => request({url:`${base}/articles/${id}/comments`,method:'POST',data}),
  deleteComment: id => request({url:`${base}/comments/${id}`,method:'DELETE'}),
  likeComment: (id, active) => request({url:`${base}/comments/${id}/like`,method:'PUT',data:{active}}),
  reportComment: (id, reason) => request({url:`${base}/comments/${id}/report`,method:'POST',data:{reason}}),
  favorites: before => request(`${base}/favorites?before=${before || 0}`),
  messages: (kind, before=0) => request(`${base}/notifications?${query({kind,before})}`),
  unread: () => request(`${base}/notifications/unread`),
  read: id => request({url:`${base}/notifications/${id}/read`,method:'POST'}),
  readAll: () => request({url:`${base}/notifications/read-all`,method:'POST'}),
};
