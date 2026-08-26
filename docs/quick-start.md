# 快速部署指南

## 今日完成功能

### 微信支付与会员系统

- **后端支付API**: `server/app/api/v1/payment.py`
- **支付服务层**: `server/app/services/payment_service.py`
- **用户模型扩展**: 新增VIP状态和配额字段
- **小程序支付页面**: `miniprogram/pages/payment/`
- **配额限制逻辑**: 每日20次免费，超出引导开通会员

### 套餐设计

| 套餐 | 价格 | 分析次数 | 有效期 |
|------|------|----------|--------|
| 月度会员 | ¥30 | 600次 | 30天 |
| 季度会员 | ¥80 | 1800次 | 90天 |
| 年度会员 | ¥268 | 7300次 | 365天 |

## 快速开始

### 1. 启动后端服务

```bash
cd server
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python main.py
```

服务将在 http://localhost:8000 启动

### 2. 打开微信开发者工具

1. 打开「微信开发者工具」
2. 导入项目 → 目录选择 `miniprogram/`
3. AppID 填写你的小程序AppID
4. 详情 → 本地设置 → 勾选「不校验合法域名」

### 3. 配置微信支付（可选）

编辑 `server/.env`:

```bash
WECHAT_APPID=你的小程序AppID
WECHAT_SECRET=你的小程序AppSecret
WECHAT_MCHID=你的商户号
WECHAT_MCHKEY=你的API密钥
WECHAT_NOTIFY_URL=https://你的域名/api/v1/payment/notify
```

编辑 `miniprogram/utils/config.js`:

```javascript
module.exports = {
  // ... 其他配置
  wechat: {
    appId: '你的小程序AppID',
  },
};
```

### 4. 开发环境测试支付

在 `miniprogram/utils/payment.js` 中确保：

```javascript
mockMode: true,  // 开发环境
```

这样支付会模拟成功，方便测试UI流程。

### 5. 切换到生产模式

```javascript
// miniprogram/utils/payment.js
mockMode: false,

// server/.env
APP_ENV=production
```

## 完整文档

- [支付接入指南](./payment-guide.md) - 详细的微信支付接入步骤
- [部署指南](./deployment.md) - 本地、Docker、生产部署
- [上线商用清单](./go-live-checklist.md) - 上线前必读

## 下一步

1. 申请微信支付商户号
2. 完成ICP备案
3. 部署到云服务器
4. 配置HTTPS域名
5. 提交小程序审核
