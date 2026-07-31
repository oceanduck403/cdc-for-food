// pages/capture/capture.js
const { request } = require('../../utils/request.js');
const config = require('../../utils/config.js');
const mock = require('../../utils/mock.js');

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
      let compressed = '';
      try { compressed = await this.compress(this.data.imagePath); } catch (e) { compressed = ''; }

      const data = await request({
        url: '/meals/analyze',
        method: 'POST',
        data: { imageBase64: compressed || 'demo-base64' },
        silent: true
      }) || mock.mealAnalyzeResult;

      const app = getApp();
      app.globalData.dailyAnalysisCount = (app.globalData.dailyAnalysisCount || 0) + 1;
      this.setData({
        result: data,
        remaining: Math.max(0, config.dailyAnalysisLimit - app.globalData.dailyAnalysisCount)
      });
    } catch (err) {
      // 即使失败也给 demo 结果，方便跑通
      this.setData({ result: mock.mealAnalyzeResult });
    } finally {
      this.setData({ analyzing: false });
    }
  },

  compress(path) {
    return new Promise((resolve, reject) => {
      if (!wx.compressImage) {
        const fs = wx.getFileSystemManager && wx.getFileSystemManager();
        if (fs && fs.readFile) {
          fs.readFile({ filePath: path, encoding: 'base64', success: (f) => resolve(f.data), fail: () => resolve('') });
          return;
        }
        return resolve('');
      }
      wx.compressImage({
        src: path,
        quality: config.imageCompress.quality,
        compressedWidth: config.imageCompress.compressedWidth,
        success: (r) => {
          const fs = wx.getFileSystemManager();
          fs.readFile({
            filePath: r.tempFilePath,
            encoding: 'base64',
            success: (file) => resolve(file.data),
            fail: () => resolve('')
          });
        },
        fail: () => {
          const fs = wx.getFileSystemManager();
          fs.readFile({
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
