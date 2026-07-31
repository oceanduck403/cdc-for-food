# 营养与食品安全 AI 小助手 · 微信小程序

原生微信小程序（不含 npm 构建），可直接在「微信开发者工具」中导入。

## 目录

```
miniprogram/
├── app.js / app.json / app.wxss     应用入口与全局配置
├── project.config.json              微信开发者工具项目配置
├── sitemap.json                     sitemap
├── pages/                           页面（每页四件套：js/wxml/wxss/json）
│   ├── index/                       首页 + 今日摄入概览
│   ├── login/                       微信授权登录 + 隐私协议
│   ├── profile/                     个人健康档案
│   ├── capture/                     拍照识膳食（成本闸口 + 压缩）
│   ├── report/                      个性化营养报告
│   ├── knowledge/                   知识库列表（分类 + 搜索）
│   ├── knowledge-detail/            知识详情
│   ├── gis-map/                     毒蘑菇 GIS 风险地图
│   └── mine/                        个人中心
├── components/                      通用组件
│   ├── nav-bar/                     自定义导航栏
│   ├── card/                        通用卡片
│   ├── section/                     区块标题
│   └── empty/                       空状态
├── utils/                           工具方法
│   ├── config.js                    常量与端点
│   ├── request.js                   HTTP 封装
│   ├── auth.js                      微信登录 / 手机号绑定 / 隐私
│   ├── storage.js                   本地存储
│   └── nutrition.js                 本地兜底的 TDEE 计算
├── styles/                          共享样式
└── images/                          图片资源（占位）
```

## 接入微信开发者工具

完整步骤、模拟器/真机调试、常见问题排查见
[`docs/miniprogram-devtools.md`](../docs/miniprogram-devtools.md)。

## 接入后端

打开 `miniprogram/utils/config.js`，将 `apiBase` 改为实际后端地址。

小程序需要在小程序管理后台配置以下合法域名：

- `request 合法域名`：后端 API 域名
- `uploadFile 合法域名`：图片上传域名（如使用对象存储直传）

开发期可在「微信开发者工具 → 详情 → 本地设置」勾选「不校验合法域名」。

## 隐私与合规

- 启动时检查 `wx.getPrivacySetting()`，未授权时调用 `wx.openPrivacyContract` 引导用户同意
- 隐私协议版本号保存在 `config.privacyVersion`，升级协议时仅需修改该常量
- 拍照识别采用图片压缩 + 每日次数上限，避免成本失控
- 涉及个人健康信息最小必要收集，仅缓存必要字段

## 开发提示

- AppID 默认使用 `touristappid`，上线前需替换为疾控中心小程序 AppID
- `lazyCodeLoading: requiredComponents` 已开启，加快首屏渲染
- 组件按需在 `pages/.../...json` 中声明