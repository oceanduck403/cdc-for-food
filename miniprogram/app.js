// app.js
const auth = require('./utils/auth.js');

App({
  globalData: {
    userInfo: null,
    token: '',
    apiBase: 'https://api.example-cdc.local/v1',
    systemInfo: null,
    dailyAnalysisCount: 0
  },

  onLaunch() {
    // 恢复登录态
    const token = wx.getStorageSync('token');
    if (token) {
      this.globalData.token = token;
    }

    // 收集系统信息
    wx.getSystemInfo({
      success: (res) => {
        this.globalData.systemInfo = res;
      }
    });

    // 隐私协议二次确认（微信要求 2023-09 起弹窗）
    if (wx.getPrivacySetting) {
      wx.getPrivacySetting({
        success: (res) => {
          if (res.needAuthorization) {
            this.popPrivacyDialog();
          }
        }
      });
    }

    // 版本更新检查
    this.checkUpdate();
  },

  onShow() {
    // 重新进入前台时刷新每日计数
    auth.refreshDailyQuota(this);
  },

  popPrivacyDialog() {
    // 微信原生隐私弹窗组件
    if (wx.openPrivacyContract) {
      wx.openPrivacyContract({
        success: () => {
          console.log('user accepted privacy contract');
        },
        fail: (err) => {
          console.warn('privacy contract error', err);
        }
      });
    }
  },

  checkUpdate() {
    if (!wx.getUpdateManager) return;
    const updateManager = wx.getUpdateManager();
    updateManager.onCheckForUpdate((res) => {
      console.log('has update?', res.hasUpdate);
    });
    updateManager.onUpdateReady(() => {
      wx.showModal({
        title: '更新提示',
        content: '新版本已就绪，是否重启应用？',
        success: (r) => {
          if (r.confirm) updateManager.applyUpdate();
        }
      });
    });
  }
});