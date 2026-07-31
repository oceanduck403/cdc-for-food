// pages/capture/capture.js
const { request } = require('../../utils/request.js');
const config = require('../../utils/config.js');

Page({
  data: {
    imagePath: '',
    analyzing: false,
    result: null,
    errorMsg: '',
    remaining: 20
  },

  onShow() {
    const app = getApp();
    this.setData({ remaining: Math.max(0, config.dailyAnalysisLimit - (app.globalData.dailyAnalysisCount || 0)) });
  },

  chooseImage() {
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      sizeType: ['compressed'],
      sourceType: ['camera', 'album'],
      success: (res) => {
        const file = res.tempFiles[0];
        this.setData({ imagePath: file.tempFilePath });
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
      wx.showToast({ title: `今日分析次数已用完`, icon: 'none' });
      return;
    }
    this.setData({ analyzing: true, errorMsg: '', result: null });

    try {
      const compressed = await this.compress(this.data.imagePath);
      const data = await request({
        url: '/meals/analyze',
        method: 'POST',
        data: { imageBase64: compressed }
      });
      const app = getApp();
      app.globalData.dailyAnalysisCount = (app.globalData.dailyAnalysisCount || 0) + 1;
      this.setData({
        result: data,
        remaining: Math.max(0, config.dailyAnalysisLimit - app.globalData.dailyAnalysisCount)
      });
    } catch (err) {
      this.setData({ errorMsg: (err && err.message) || '分析失败，请稍后重试' });
    } finally {
      this.setData({ analyzing: false });
    }
  },

  compress(path) {
    return new Promise((resolve) => {
      wx.compressImage({
        src: path,
        quality: config.imageCompress.quality,
        compressedWidth: config.imageCompress.compressedWidth,
        success: (r) => {
          wx.getFileSystemManager().readFile({
            filePath: r.tempFilePath,
            encoding: 'base64',
            success: (file) => resolve(file.data)
          });
        },
        fail: () => {
          wx.getFileSystemManager().readFile({
            filePath: path,
            encoding: 'base64',
            success: (file) => resolve(file.data),
            fail: () => resolve('')
          });
        }
      });
    });
  },

  viewReport() {
    if (!this.data.result) return;
    wx.navigateTo({
      url: `/pages/report/report?id=${this.data.result.mealId || ''}`
    });
  }
});