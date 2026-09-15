const navigation = require('../../utils/navigation.js');
// pages/capture/capture.js
const config = require('../../utils/config.js');
const qwen = require('../../utils/qwen.js');

Page({
  data: {
    imagePath: '',
    analyzing: false,
    result: null,
    errorMsg: '',
    remaining: 20,
    dailyLimit: 20
  },

  onShow() {
    const app = getApp();
    this.setData({
      remaining: Math.max(0, config.dailyAnalysisLimit - (app.globalData.dailyAnalysisCount || 0))
    });
  },

  chooseImage() {
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      sizeType: ['compressed'],
      sourceType: ['camera', 'album'],
      success: (res) => {
        const file = res.tempFiles && res.tempFiles[0];
        if (file) this.setData({ imagePath: file.tempFilePath, errorMsg: '', result: null });
      },
      fail: () => {}
    });
  },

  async analyze() {
    if (!this.data.imagePath) {
      wx.showToast({ title: '请先选择图片', icon: 'none' });
      return;
    }
    if (this.data.remaining <= 0) {
      wx.showToast({ title: '今日分析次数已用完', icon: 'none' });
      return;
    }
    this.setData({ analyzing: true, errorMsg: '', result: null });

    try {
      const data = await qwen.analyzeFoodFromImage(this.data.imagePath);

      const app = getApp();
      app.globalData.dailyAnalysisCount = (app.globalData.dailyAnalysisCount || 0) + 1;

      // 补全汇总字段（兼容千问直接返回 items[] 的情况）
      const items = data.items || [];
      const totalKcal    = data.totalKcal    || items.reduce((s, i) => s + (i.kcal    || 0), 0);
      const totalProtein = data.totalProtein || items.reduce((s, i) => s + (i.protein || 0), 0);
      const totalFat     = data.totalFat     || items.reduce((s, i) => s + (i.fat     || 0), 0);
      const totalCarbs   = data.totalCarbs   || items.reduce((s, i) => s + (i.carbs   || 0), 0);
      const totalSodium  = data.totalSodium  || 0;
      const enriched = { ...data, items, totalKcal, totalProtein, totalFat, totalCarbs, totalSodium };

      // 给每个 item 加上热量占比
      enriched.items = items.map((item, idx) => ({
        ...item,
        percent: totalKcal > 0 ? Math.round((item.kcal / totalKcal) * 100) : 0,
      }));

      this.setData({
        result: enriched,
        remaining: Math.max(0, config.dailyAnalysisLimit - app.globalData.dailyAnalysisCount)
      });
    } catch (err) {
      console.error('[capture] 分析异常', err);
      this.setData({
        result: null,
        errorMsg: '识别服务暂时不可用，请稍后重试'
      });
    } finally {
      this.setData({ analyzing: false });
    }
  },

  viewReport() {
    if (!this.data.result) return;
    navigation.open({
      url: `/pages/report/report?id=${this.data.result.mealId || ''}`
    });
  },

});
