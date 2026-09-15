const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function makePage(name, community) {
  let definition;
  const nav = [];
  const toasts = [];
  const wx = {
    showToast: options => toasts.push(options.title), stopPullDownRefresh() {},
    showModal: options => options.success({confirm:true}),
    showActionSheet: options => options.success({tapIndex:0})
  };
  const sandbox = {
    Page: value => definition = value,
    wx, console, setTimeout, clearTimeout,
    require: name => name.includes('community.js') ? community
      : name.includes('navigation.js') ? {open:url => nav.push(typeof url === 'string' ? url : url.url)}
      : name.includes('request.js') ? {request:async()=>({})} : {}
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, `../pages/${name}/${name}.js`), 'utf8'), sandbox);
  const page = {...definition, data:JSON.parse(JSON.stringify(definition.data))};
  page.setData = (change, callback) => {Object.assign(page.data, change); if(callback) callback();};
  return {page, nav, toasts};
}

const formatArticle = value => ({...value, date:'2026-09-14'});
const dateLabel = value => value || '';

test('科普列表从真实文章接口读取互动状态，点赞成功后使用服务端返回值', async () => {
  let state = {id:1,title:'健康知识',category:'guide',likeCount:0,commentCount:2,liked:false,favorited:false};
  const community = {formatArticle, requireLogin:()=>true,
    articles:async()=>({items:[state],hasMore:false,nextCursor:0}),
    react:async(id,kind,active)=>{assert.equal(id,1);assert.equal(kind,'like');state={...state,liked:active,likeCount:1};return state;}};
  const {page}=makePage('science',community);
  await page.load();
  assert.equal(page.data.list[0].commentCount,2);
  await page.likeArticle({currentTarget:{dataset:{id:1}}});
  assert.equal(page.data.list[0].liked,true);
  assert.equal(page.data.list[0].likeCount,1);
});

test('文章详情发布评论使用同一个幂等请求号重试，并刷新评论数', async () => {
  const attempts=[];let fail=true;let commentCount=0;
  const community = {formatArticle,dateLabel,requireLogin:()=>true,
    article:async()=>({id:1,title:'健康知识',category:'guide',commentCount}),
    comments:async()=>({items:[],hasMore:false,nextCursor:0}),
    comment:async(id,body)=>{attempts.push(body);if(fail){fail=false;throw Error('网络断开');}commentCount=1;return{id:5};}};
  const {page}=makePage('knowledge-detail',community);page.onLoad({id:'1'});
  await page.refresh();page.onCommentInput({detail:{value:'内容很好'}});
  await page.submitComment();await page.submitComment();
  assert.equal(attempts.length,2);
  assert.equal(attempts[0].request_id,attempts[1].request_id);
  assert.equal(page.data.article.commentCount,1);
  assert.equal(page.data.commentText,'');
});

test('消息筛选、已读与跳转原文连接真实文章', async () => {
  const reads=[];let kindSeen='';
  const community = {loggedIn:()=>true,dateLabel,
    messages:async kind=>{kindSeen=kind;return {items:[{id:8,kind:'reply',actor:'张医生',self:false,articleId:3,articleTitle:'健康文章',read:false}],hasMore:false,nextCursor:0};},
    unread:async()=>({count:1}),read:async id=>reads.push(id)};
  const {page,nav}=makePage('messages',community);await page.refresh();
  page.setData({filter:'received'});await page.refresh();assert.equal(kindSeen,'received');
  await page.openMessage({currentTarget:{dataset:{id:8}}});
  assert.equal(reads[0],8);assert.equal(page.data.unreadCount,0);
  assert.equal(nav[0],'/pages/knowledge-detail/knowledge-detail?id=3');
});

test('收藏列表取消收藏后移除当前文章', async () => {
  const reactions=[];
  const community = {loggedIn:()=>true,formatArticle,
    favorites:async()=>({items:[{id:5,title:'膳食文章'}],hasMore:false,nextCursor:0}),
    react:async(...args)=>reactions.push(args)};
  const {page}=makePage('favorites',community);await page.refresh();
  await page.removeFavorite({currentTarget:{dataset:{id:5}}});
  assert.equal(page.data.items.length,0);
  assert.equal(JSON.stringify(reactions[0]),JSON.stringify([5,'favorite',false]));
});

test('科普列表按后端游标继续加载，不重复展示第一页', async () => {
  const cursors=[];
  const community={formatArticle,requireLogin:()=>true,articles:async params=>{
    cursors.push(params.before || 0);
    return params.before ? {items:[{id:1,category:'guide'}],hasMore:false,nextCursor:0}
      : {items:[{id:2,category:'guide'}],hasMore:true,nextCursor:2};
  }};
  const {page}=makePage('science',community);
  await page.load();await page.loadMore();
  assert.equal(JSON.stringify(cursors),JSON.stringify([0,2]));
  assert.equal(page.data.list.map(item=>item.id).join(','),'2,1');
  assert.equal(page.data.listHasMore,false);
});

test('未登录时消息和收藏页不请求私人数据，举报仅提交选中原因', async () => {
  let privateCalls=0;
  const guest={loggedIn:()=>false,messages:async()=>privateCalls++,favorites:async()=>privateCalls++};
  makePage('messages',guest).page.onShow();makePage('favorites',guest).page.onShow();
  assert.equal(privateCalls,0);
  const reports=[];
  const community={requireLogin:()=>true,reportComment:async(id,reason)=>reports.push([id,reason])};
  const {page}=makePage('knowledge-detail',community);
  page.reportComment({currentTarget:{dataset:{id:12}}});
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(JSON.stringify(reports),JSON.stringify([[12,'垃圾广告']]));
});
