# 微信支付接入指南

## 概述

本系统采用微信支付「Native支付」模式（商户下单 → 用户支付 → 微信回调），实现会员套餐购买功能。

## 架构流程

```
用户选择套餐 → 小程序调起支付 → 微信支付成功 → 回调通知 → 更新用户配额
```

## 前置条件

### 1. 开通微信支付

1. **申请商户号**
   - 微信支付商户平台：https://pay.weixin.qq.com
   - 需要企业主体（个体工商户也可）
   - 签约微信支付产品

2. **配置AppID绑定**
   - 在商户平台将小程序AppID与商户号绑定
   - 小程序后台 → 微信支付 → 关联商户号

### 2. 获取配置信息

| 配置项 | 说明 | 获取位置 |
|--------|------|----------|
| WECHAT_APPID | 小程序AppID | 微信公众平台 |
| WECHAT_SECRET | 小程序AppSecret | 微信公众平台 |
| WECHAT_MCHID | 商户号 | 商户平台 |
| WECHAT_MCHKEY | 商户密钥 | 商户平台（设置API密钥） |

## 配置步骤

### 后端配置

编辑 `server/.env` 文件：

```bash
# 微信小程序
WECHAT_APPID=wx1234567890abcdef
WECHAT_SECRET=your_appsecret_here

# 微信支付
WECHAT_MCHID=1234567890
WECHAT_MCHKEY=your_32位API密钥_here
WECHAT_NOTIFY_URL=https://your-domain.com/api/v1/payment/notify
```

### 前端配置

编辑 `miniprogram/utils/config.js`：

```javascript
module.exports = {
  // ... 其他配置
  wechat: {
    appId: 'wx1234567890abcdef',
  },
  // 模拟支付模式（开发环境设为true）
  payment: {
    mockMode: false,  // 生产环境设为false
  },
};
```

## 套餐设计

| 套餐 | 价格 | 次数 | 有效期 | 特点 |
|------|------|------|--------|------|
| 月度会员 | ¥30 | 600次 | 30天 | 适合短期试用 |
| 季度会员 | ¥80 | 1800次 | 90天 | 性价比最高 |
| 年度会员 | ¥268 | 7300次 | 365天 | 适合长期用户 |

## 开发测试

### 本地测试

1. 设置 `mockMode: true` 启用模拟支付
2. 创建订单后会自动模拟支付成功
3. 可验证UI交互和状态更新逻辑

### 沙箱环境

微信支付提供沙箱环境用于测试：
- 商户平台 → 产品中心 → 开发配置 → 沙箱环境
- 使用沙箱密钥替换正式密钥

### 回调测试

使用内网穿透工具（如 ngrok）测试回调：

```bash
ngrok http 8000
# 将返回的公网URL配置为 WECHAT_NOTIFY_URL
```

## 生产部署检查清单

- [ ] 已配置正式环境 `.env`
- [ ] 已将 `mockMode` 设为 `false`
- [ ] 回调地址 `WECHAT_NOTIFY_URL` 已启用 HTTPS
- [ ] 已在商户平台配置正确的API密钥
- [ ] 已测试完整支付流程
- [ ] 已配置支付成功通知模板消息（可选）

## 费用说明

微信支付手续费：
- 普通商户：0.6%（单笔最低0.1元）
- 特殊行业（餐饮等）：0.7%~1%

示例：
- 月度会员 ¥30：手续费约 ¥0.18，到账 ¥29.82
- 年度会员 ¥268：手续费约 ¥1.61，到账 ¥266.39

## 常见问题

### Q: 支付提示"商户未开通该支付方式"
A: 检查商户平台是否已开通 JSAPI 支付产品

### Q: 回调通知接收不到
A: 检查：
1. 回调URL是否公网可访问
2. HTTPS证书是否有效
3. 防火墙是否放行80/443端口

### Q: 签名验证失败
A: 检查API密钥是否正确，注意大小写

## 相关文档

- [微信支付开发文档](https://pay.weixin.qq.com/wiki/doc/apiv3/index.shtml)
- [小程序支付流程](https://developers.weixin.qq.com/miniprogram/dev/platform-capabilities/business-capabilities/payment.html)
