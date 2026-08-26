// pages/payment/payment.js
const { request } = require('../../utils/request.js');
const config = require('../../utils/config.js');

Page({
  data: {
    isLogin: false,
    isVip: false,
    remaining: 0,
    expireDate: '',
    dailyLimit: 20,
    packages: [
      { id: 1, name: '月度会员', description: '30天内有效，每天20次', analysisCount: 600, priceYuan: 30, validDays: 30 },
      { id: 2, name: '季度会员', description: '90天内有效，每天20次', analysisCount: 1800, priceYuan: 80, validDays: 90 },
      { id: 3, name: '年度会员', description: '365天内有效，每天20次', analysisCount: 7300, priceYuan: 268, validDays: 365 },
    ],
    selectedPackage: 1,
    selectedPrice: 30,
    paying: false,
  },

  onLoad() {
    // 检查登录状态
    const token = wx.getStorageSync('token');
    const profile = wx.getStorageSync('profile');
    
    if (token && profile) {
      this.setData({
        isLogin: true,
        isVip: profile.isVip || false,
        remaining: profile.remainingCount || 0,
        expireDate: profile.vipExpireAt || '',
      });
      this.fetchQuota();
    }

    // 获取套餐列表
    this.fetchPackages();
  },

  onShow() {
    // 刷新配额
    if (this.data.isLogin) {
      this.fetchQuota();
    }
  },

  async fetchQuota() {
    try {
      const res = await request({ url: '/users/me/quota', silent: true });
      if (res) {
        this.setData({
          remaining: res.remaining || 0,
          isVip: res.isVip || false,
          expireDate: res.expireAt || '',
        });
      }
    } catch (e) {
      // 使用本地配置
      this.setData({
        remaining: config.dailyAnalysisLimit,
        dailyLimit: config.dailyAnalysisLimit,
      });
    }
  },

  async fetchPackages() {
    try {
      const res = await request({ url: '/payment/packages', silent: true });
      if (res && Array.isArray(res) && res.length > 0) {
        // 将分转换为元
        const packages = res.map(pkg => ({
          ...pkg,
          priceYuan: Math.round(pkg.price_yuan / 100),
          analysisCount: pkg.analysis_count,
          description: pkg.description,
        }));
        this.setData({
          packages,
          selectedPackage: packages[0].id,
          selectedPrice: packages[0].priceYuan,
        });
      }
    } catch (e) {
      // 使用默认套餐（价格已转换为元）
      console.log('使用默认套餐');
    }
  },

  selectPackage(e) {
    const id = e.currentTarget.dataset.id;
    const pkg = this.data.packages.find(p => p.id === id);
    if (pkg) {
      this.setData({
        selectedPackage: id,
        selectedPrice: pkg.priceYuan,
      });
    }
  },

  goLogin() {
    wx.navigateTo({ url: '/pages/login/login' });
  },

  async startPayment() {
    if (!this.data.isLogin) {
      this.goLogin();
      return;
    }

    if (this.data.paying) return;

    this.setData({ paying: true });

    try {
      // 创建支付订单
      const res = await request({
        url: '/payment/create',
        method: 'POST',
        data: { package_id: this.data.selectedPackage },
        silent: true,
      });

      if (!res || !res.payment_params) {
        throw new Error('订单创建失败');
      }

      const params = res.payment_params;

      // 模拟支付成功（开发环境）
      if (params.mock) {
        wx.showModal({
          title: '开发模式',
          content: `模拟支付成功！\n订单号：${params.order_id}\n套餐：${params.package_name}`,
          showCancel: false,
          success: () => {
            this.handlePaymentSuccess(params.order_id);
          }
        });
        return;
      }

      // 真实微信支付
      wx.requestPayment({
        timeStamp: params.timeStamp,
        nonceStr: params.nonceStr,
        package: params.package,
        signType: params.signType,
        paySign: params.paySign,
        success: (payRes) => {
          console.log('支付成功', payRes);
          this.handlePaymentSuccess(res.order_id);
        },
        fail: (err) => {
          console.log('支付取消或失败', err);
          wx.showToast({
            title: err.errMsg === 'requestPayment:fail cancel' ? '已取消支付' : '支付失败',
            icon: 'none'
          });
        }
      });
    } catch (err) {
      console.error('支付异常', err);
      wx.showToast({
        title: '创建订单失败',
        icon: 'none'
      });
    } finally {
      this.setData({ paying: false });
    }
  },

  async handlePaymentSuccess(orderId) {
    // 更新本地用户状态
    const profile = wx.getStorageSync('profile') || {};
    
    // 更新为VIP状态
    const pkg = this.data.packages.find(p => p.id === this.data.selectedPackage);
    const expireDate = new Date();
    expireDate.setDate(expireDate.getDate() + (pkg ? pkg.validDays : 30));

    const updatedProfile = {
      ...profile,
      isVip: true,
      vipExpireAt: expireDate.toISOString().split('T')[0],
      remainingCount: (profile.remainingCount || 0) + (pkg ? pkg.analysisCount : 600),
    };

    wx.setStorageSync('profile', updatedProfile);

    // 更新App全局数据
    const app = getApp();
    if (app && app.globalData) {
      app.globalData.isVip = true;
      app.globalData.profile = updatedProfile;
    }

    this.setData({
      isVip: true,
      expireDate: updatedProfile.vipExpireAt,
      remaining: updatedProfile.remainingCount,
    });

    wx.showModal({
      title: '🎉 开通成功',
      content: `恭喜您已开通「${pkg ? pkg.name : '会员'}」！\n有效期至 ${updatedProfile.vipExpireAt}\n剩余 ${updatedProfile.remainingCount} 次分析`,
      showCancel: false,
      success: () => {
        // 返回上一页
        wx.navigateBack();
      }
    });
  },

  onShareAppMessage() {
    return {
      title: '营养与食品安全AI小助手 - 开通会员',
      path: '/pages/payment/payment',
    };
  }
});
