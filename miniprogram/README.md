# 膳知有伴 · 微信小程序前端

原生 JavaScript/CommonJS、WXML、WXSS，使用微信 `Page`、`Component` 和原生 API，没有 React/Vue/uni-app 运行依赖。

## 当前页面

`app.json` 注册 19 个页面，底栏为健康评估、打卡指导、AI 科普、科普互动、我的；启动页为微信登录。管理员使用独立登录入口。医生/GIS 等历史页面源码保留，但未注册到当前用户版。

- 健康评估：原始五表、动态题目、分页/跳题、时间/小数、草稿和历史。
- 打卡指导：膳食/运动/饮水记录、三项进度、七日足迹及鼓励反馈。
- AI 科普：文字问答、快捷问题、图片分析入口及本机对话历史；悬浮按钮支持拖动吸边并进入 AI 页。
- 科普互动：后端文章、点赞/收藏/评论/回复、消息与收藏入口；无患者素材发布入口。
- 我的：头像/昵称及健康资料、隐私条款、退出和注销。
- 管理员：概览、用户、模板元数据/启停及提交记录、修改账号密码；没有完整题目编辑器和文章 CMS。

## 网络与存储

`utils/transport.js` 统一直连和 CloudBase 传输适配。`utils/api.js`、`utils/request.js` 两套上层封装并存，共用传输层。源码 `useMock=false`、`release-runtime.js` 为未配置状态，开发版通过本机存储覆盖接口地址；正式包使用构建注入的 HTTPS 地址。

打卡、草稿、AI 对话和位置存微信本地存储，不能视为云端跨设备同步。AI Key 仅保存在服务端。当前前端 AI 页本机限额与服务端配额存在差异，需后续统一。

## 运行、构建和测试

微信开发者工具导入仓库根目录，由根 `project.config.json` 定位此目录。完整步骤见 [本地预览手册](../docs/miniprogram-devtools.md)，架构与接手说明见 [技术交接文档](../docs/technical-handoff.md)。

在仓库根目录运行前端测试：

```powershell
node --test miniprogram/tests/*.test.js
```

正式包构建说明见 [自建服务构建手册](../deploy/selfhost/README.md)。图标来源与许可见 [SOURCES.md](images/ui/SOURCES.md)：Ant Design Icons SVG 4.6.0/MIT，本地 PNG 导出；阿里巴巴矢量图标库作为风格参考。
