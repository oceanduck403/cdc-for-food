// utils/request.js
const config = require('./config.js');
const mock = require('./mock.js');

// 简易 URL → mock 数据 路由（按 URL 前缀匹配）
const mockRoutes = [
  { match: /\/reports\/today$/, data: () => mock.todaySummary },
  { match: /\/knowledge(\?.*)?$/, data: (url) => {
    // 外部知识库模式
    if (config.knowledgeBase && config.knowledgeBase.enabled) {
      return fetchExternalKnowledge(url);
    }
    const u = new URL(url.startsWith('http') ? url : 'http://x' + url);
    const cat = u.searchParams.get('category') || 'guide';
    const list = (mock.knowledgeMap[cat] || mock.knowledgeMap.guide).items;
    return { items: list };
  }},
  { match: /\/knowledge\/(.+)$/, data: (url) => {
    // 外部知识库模式
    if (config.knowledgeBase && config.knowledgeBase.enabled) {
      return fetchExternalArticle(url);
    }
    const m = url.match(/\/knowledge\/([^?&#/]+)/);
    const id = m ? m[1] : '';
    return mock.knowledgeArticles[id] || {
      id,
      title: '示例文章',
      source: '演示数据',
      updatedAt: '2026-07-30',
      contentHtml: '<p style="line-height:1.7">这是演示内容，请接入真实知识库。</p>'
    };
  }},
  { match: /\/gis\/mushroom-risk\?/, data: () => mock.mushroomMarkers },
  { match: /\/gis\/mushroom-risk\/(.+)$/, data: (url) => {
    const m = url.match(/\/gis\/mushroom-risk\/([^?&#/]+)/);
    const id = m ? m[1] : '';
    const hit = (mock.mushroomMarkers.items || []).find((x) => x.id === id);
    return hit ? {
      id: hit.id, name: hit.name, species: hit.species,
      level: hit.level, period: hit.period,
      description: `${hit.name} 周边历史上发生过误采误食事件，请勿采摘野生菌。`
    } : { id, name: '未知点位', level: '—', description: '暂无数据' };
  }},
  { match: /\/users\/me\/quota$/, data: () => mock.dailyQuota },
  { match: /\/users\/me$/, data: () => mock.profile },
  { match: /\/meals\/analyze$/, data: () => mock.mealAnalyzeResult, method: 'POST' },
  { match: /\/meals\/.*\/report$/, data: () => mock.mealReport },
  { match: /\/auth\/wechat$/, data: () => ({
    token: 'demo-token-2026-07-31',
    profile: mock.profile
  }), method: 'POST' }
];

// 外部知识库：获取文章列表
async function fetchExternalKnowledge(url) {
  const u = new URL(url.startsWith('http') ? url : 'http://x' + url);
  const category = u.searchParams.get('category') || 'guide';
  
  try {
    const resp = await wx.request({
      url: `${config.knowledgeBase.baseUrl}/knowledge-index.json`,
      method: 'GET'
    });
    
    if (resp.statusCode === 200 && resp.data) {
      const catData = resp.data[category];
      if (catData && catData.items) {
        return { items: catData.items };
      }
    }
  } catch (e) {
    console.error('外部知识库加载失败', e);
  }
  
  // 降级到 mock
  const list = (mock.knowledgeMap[category] || mock.knowledgeMap.guide).items;
  return { items: list };
}

// 外部知识库：获取单篇文章
async function fetchExternalArticle(url) {
  const m = url.match(/\/knowledge\/([^?&#/]+)/);
  const id = m ? m[1] : '';
  
  try {
    const resp = await wx.request({
      url: `${config.knowledgeBase.baseUrl}/knowledge.json`,
      method: 'GET'
    });
    
    if (resp.statusCode === 200 && resp.data && resp.data.items) {
      const article = resp.data.items.find(item => item.id === id);
      if (article) {
        return {
          id: article.id,
          title: article.title,
          source: article.source,
          updatedAt: article.updatedAt,
          contentHtml: `<p>${article.summary}</p><p><a href="${article.originalUrl}">阅读原文</a></p>`
        };
      }
    }
  } catch (e) {
    console.error('外部知识库加载失败', e);
  }
  
  // 降级到 mock
  return mock.knowledgeArticles[id] || {
    id,
    title: '文章不存在',
    source: '未知来源',
    updatedAt: new Date().toISOString().split('T')[0],
    contentHtml: '<p>无法加载文章内容，请稍后重试。</p>'
  };
}

function findMock(url, method) {
  for (const r of mockRoutes) {
    if (r.match.test(url) && (!r.method || r.method === method)) {
      return r.data(url);
    }
  }
  return null;
}

function request({ url, method = 'GET', data = {}, header = {}, showLoading = true, silent = false }) {
  const app = getApp();
  const token = (app && app.globalData && app.globalData.token) || wx.getStorageSync('token') || '';

  if (showLoading) {
    wx.showLoading({ title: '加载中', mask: true });
  }

  // mock 模式：完全本地走数据，不发请求
  if (config.useMock && !url.startsWith('http')) {
    const payload = findMock(url, method);
    if (showLoading) wx.hideLoading();
    return mock.delay(payload, 220);
  }

  return new Promise((resolve, reject) => {
    wx.request({
      url: (url.startsWith('http') ? '' : config.apiBase) + url,
      method,
      data,
      header: Object.assign(
        { 'content-type': 'application/json' },
        header,
        token ? { Authorization: `Bearer ${token}` } : {}
      ),
      success(res) {
        if (showLoading) wx.hideLoading();
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data);
        } else if (res.statusCode === 401) {
          app.globalData.token = '';
          wx.removeStorageSync('token');
          if (!silent) wx.showToast({ title: '请重新登录', icon: 'none' });
          reject(res.data);
        } else {
          if (!silent) {
            wx.showToast({
              title: (res.data && res.data.message) || `请求失败 ${res.statusCode}`,
              icon: 'none'
            });
          }
          reject(res.data || res);
        }
      },
      fail(err) {
        if (showLoading) wx.hideLoading();
        // 真实网络失败 + mock 开启 → 静默 fallback
        if (config.useMock && !url.startsWith('http')) {
          const payload = findMock(url, method);
          if (payload !== null) {
            resolve(mock.delay(payload, 120));
            return;
          }
        }
        if (!silent) wx.showToast({ title: '网络异常', icon: 'none' });
        reject(err);
      }
    });
  });
}

module.exports = { request };
