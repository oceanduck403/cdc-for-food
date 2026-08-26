// pages/index/index.js
const { request } = require('../../utils/request.js');

const TIPS = [
  '夏季气温升高，食物易滋生细菌，建议剩菜剩饭及时冷藏并在24小时内食用完毕。',
  '野生蘑菇不要随意采摘食用，我国已发现毒蘑菇400余种，中毒后无特效解毒药。',
  '生熟食品分开存放，避免交叉污染，切菜时建议先切熟食再切生食。',
  '发芽土豆、未煮熟的四季豆、鲜黄花菜均含天然毒素，请务必充分加热后再食用。',
  '外出就餐时优先选择量化等级为"笑脸"（A级）的餐饮单位。',
  '亚硝酸盐易在腌渍蔬菜中积累，建议腌渍20天后再食用，且不宜过量。',
  '冷链食品请在购买后2小时内放入冰箱，避免长时间室温放置。',
];

const QUICK_ENTRIES = [
  {
    iconText: '📷',
    label: '拍照识膳食',
    desc: 'AI 智能分析食物营养',
    path: '/pages/capture/capture',
    bgColor: '#E8F5F0',
  },
  {
    iconText: '📚',
    label: '营养知识',
    desc: '膳食指南与食品安全',
    path: '/pages/knowledge/knowledge',
    bgColor: '#FEF3C7',
  },
  {
    iconText: '🗺️',
    label: '毒蘑菇地图',
    desc: '周边风险点位早知道',
    path: '/pages/gis-map/gis-map',
    bgColor: '#FEE2E2',
  },
  {
    iconText: '👤',
    label: '健康档案',
    desc: '个性化营养需求评估',
    path: '/pages/profile/profile',
    bgColor: '#EDE9FE',
  },
];

Page({
  data: {
    greeting: '早上好',
    todayDate: '',
    quickEntries: QUICK_ENTRIES,
    todayCalories: 0,
    todayTarget: 2000,
    heatPercent: 0,
    remaining: 20,
    remainingClass: 'low',
    tipOfDay: TIPS[0],
  },

  onShow() {
    const now = new Date();
    this.setData({
      greeting: this.computeGreeting(),
      todayDate: `${now.getMonth() + 1}月${now.getDate()}日 ${['周日','周一','周二','周三','周四','周五','周六'][now.getDay()]}`,
      tipOfDay: TIPS[Math.floor(Math.random() * TIPS.length)],
    });
    this.loadTodaySummary();
    this.updateRemaining();
  },

  computeGreeting() {
    const h = new Date().getHours();
    if (h < 6) return '夜深了，注意休息';
    if (h < 11) return '早上好';
    if (h < 14) return '中午好';
    if (h < 18) return '下午好';
    return '晚上好';
  },

  updateRemaining() {
    const app = getApp();
    const used = (app && app.globalData && app.globalData.dailyAnalysisCount) || 0;
    const remaining = Math.max(0, 20 - used);
    const cls = remaining === 0 ? 'over' : remaining < 5 ? 'warn' : 'low';
    this.setData({ remaining, remainingClass: cls });
  },

  loadTodaySummary() {
    request({ url: '/reports/today', showLoading: false, silent: true })
      .then((data) => {
        const calories = (data && data.calories) || 0;
        const target = (data && data.target) || 2000;
        const pct = Math.min(100, Math.round((calories / target) * 100));
        this.setData({
          todayCalories: calories,
          todayTarget: target,
          heatPercent: pct,
        });
        // 绘制环形进度
        this.drawRing(pct);
      })
      .catch(() => {
        this.setData({ heatPercent: 0 });
        this.drawRing(0);
      });
  },

  drawRing(percent) {
    const ctx = wx.createCanvasContext('calorieRing');
    const W = 240; // 2x canvas size
    const cx = W / 2, cy = W / 2, R = 44;
    const startAngle = -Math.PI / 2;
    const endAngle = startAngle + (percent / 100) * 2 * Math.PI;

    // 背景弧
    ctx.beginPath();
    ctx.arc(cx, cy, R, 0, 2 * Math.PI);
    ctx.setStrokeStyle('rgba(255,255,255,0.2)');
    ctx.setLineWidth(10);
    ctx.stroke();

    // 进度弧
    if (percent > 0) {
      ctx.beginPath();
      ctx.arc(cx, cy, R, startAngle, endAngle);
      ctx.setStrokeStyle('#FFFFFF');
      ctx.setLineWidth(10);
      ctx.setLineCap('round');
      ctx.stroke();
    }

    ctx.draw();
  },

  goTo(e) {
    const { path } = e.currentTarget.dataset;
    if (!path) return;
    if (path.startsWith('/pages/')) {
      wx.navigateTo({ url: path });
    }
  }
});
