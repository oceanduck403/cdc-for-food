# 小程序本地预览手册（微信开发者工具）

目标：把 `miniprogram/` 目录在「微信开发者工具」里导入并跑通，以便后续接入真实后端、调试业务逻辑、扫码真机预览。

## 1. 前置准备

### 1.1 安装微信开发者工具

- 下载地址：<https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html>
- Windows 选择 `wechat_devtools_<版本>.exe` 安装包
- macOS 选择 `wechat_devtools_<版本>.dmg`
- 安装后使用**微信扫码登录**（必须用项目负责人的微信，否则扫码确认权限会失败）

### 1.2 AppID（小程序账号）

小程序必须先有 AppID 才能发布，本地预览则可使用「测试号」。

| 场景 | 建议 |
| --- | --- |
| 个人学习 / 内部联调 | 使用**测试号**，无需注册 |
| 真实接入甲方小程序 | 在 [微信公众平台](https://mp.weixin.qq.com) 注册「小程序」账号，记下 AppID |
| 已注册主体复用 | 直接使用现有 AppID |

> 小程序类目建议选 **医疗 → 健康保健类目**，否则后续 `wx.getLocation`、`chooseMedia` 等权限可能被拒。

## 2. 导入项目

1. 打开「微信开发者工具」
2. 左侧扫码登录
3. 选择 **小程序项目 → 导入项目**（不要选「小游戏」「公众号网页」等）
4. 填写：

   | 字段 | 值 |
   | --- | --- |
   | 项目名称 | `nutrition-ai-miniprogram`（或自定义） |
   | 目录 | 选择仓库内的 `miniprogram/` 文件夹 |
   | AppID | 测试号或真实 AppID |
   | 开发模式 | **小程序** |
   | 后端服务 | **不使用云服务**（我们的后端是独立 FastAPI） |

5. 点击「确定」→ 项目首次编译

> 若弹出「当前开发者工具版本过旧，请升级」提示，请下载最新稳定版。

## 3. 启用本地调试选项

进入项目后：

1. 顶部菜单 → **详情**
2. 切到 **本地设置** Tab
3. 勾选以下项以便本地联调：

   - ☑ 不校验合法域名、web-view（业务域名）、TLS 版本以及 HTTPS 证书
   - ☑ 不校验请求域名及 TLS 版本
   - ☑ 启用多核心编译
   - ☑ 启用自定义处理命令（可选）

> 这些勾选项只在「本地」生效，发布到正式环境仍需在公众平台配置合法域名。

## 4. 配置后端地址

打开 `miniprogram/utils/config.js`：

```js
module.exports = {
  apiBase: 'http://localhost:8000/v1',  // 本地后端
  // ...
};
```

> 微信开发者工具中 `localhost` 会被解析为本机，可直接访问；真机预览时需替换为局域网 IP（如 `http://192.168.1.100:8000/v1`）或公网 HTTPS 地址。

### 4.1 真机预览常见坑

- 真机无法访问 `localhost` → 改成电脑的局域网 IP
- 局域网请求被拒 → 在开发者工具「详情 → 项目设置」里把局域网 IP 加入「request 合法域名」（即使是测试号也要在工具的「不校验合法域名」勾选上）
- 后端启用了 HTTPS 但证书是自签名 → 勾选「不校验合法域名」临时绕开

## 5. 启动后端（可选）

如果只是前端联调，可以暂时让所有 `/api/*` 请求失败（页面会降级展示空态）。

需要真后端时：

```bash
cd server
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python -m app.db.init_db        # 初始化 SQLite + seed 数据
python main.py                  # 监听 0.0.0.0:8000
```

后端日志会显示：

```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

Swagger 文档：<http://localhost:8000/docs>

## 6. 真机预览

1. 点击开发者工具顶部 **预览** 按钮（手机图标）
2. 弹出二维码 → 用绑定的微信扫码
3. 手机端弹出体验版小程序（绑定微信必须是该 AppID 的开发者 / 体验成员）
4. 真机日志：在工具中通过 **调试 → 远程调试** 查看 `vConsole`

> 测试号只能由开发者本人扫码预览。正式预览需在公众平台「成员管理 → 体验成员」中加入测试微信号。

## 7. 模拟器调试技巧

### 7.1 网络请求调试

- 工具右上角 **Network 面板** 查看所有 `wx.request` 请求
- 点击请求查看 Request / Response / Header
- 后端未返回时检查：是否勾选了「不校验合法域名」、`apiBase` 是否正确

### 7.2 控制台调试

- 工具底部 **Console 面板** 等同于 `console.log`
- 真机调试：在手机端通过屏幕右上角「···」打开 vConsole
- 日志输出受微信隐私接口限制，敏感信息不会自动脱敏，**上线前必须移除调试日志**

### 7.3 Storage 检查

- 工具 → 调试 → **Storage 面板** 查看本地缓存
- 常用键：`token` / `profile` / `privacy_accepted`

### 7.4 模拟器 vs 真机差异

| 能力 | 模拟器 | 真机 |
| --- | --- | --- |
| 拍照 / 相册 | 部分支持 | 完整 |
| 位置授权 | 模拟定位 | 真实定位 |
| 蓝牙 / NFC | 不支持 | 完整 |
| 性能 | 接近真机 | - |

## 8. 常见问题排查

### Q1 编译报错 `app.json: pages 字段必须是字符串数组`

- `app.json` 的 `pages` 字段被改成了对象，请恢复为字符串数组
- 检查路径：每个页面路径必须以 `/` 开头、不要写 `.js` 后缀

### Q2 `Error: touristappid is not a valid AppID`

- 当前 `project.config.json` 里 `appid: "touristappid"` 是占位符
- 在开发者工具右上角 **详情 → 基础信息** 直接修改 AppID
- 或者把 `project.config.json` 改成自己的 AppID 后重启项目

### Q3 接口报 `不在以下 request 合法域名列表中`

- 工具菜单 → 详情 → 本地设置 → 勾选「不校验合法域名」
- 正式发布前必须在公众平台「开发 → 开发管理 → 服务器域名」配置 HTTPS 域名

### Q4 `wx.openPrivacyContract is not a function`

- 微信基础库版本过低，请升级到 ≥ 3.0.0（开发者工具右上角可切换）
- `project.config.json` 中 `libVersion` 已设为 `3.0.0`

### Q5 地图空白 / 没有 markers

- 检查 `app.json` 中是否声明了位置相关权限（已默认开启 `getLocation`）
- 检查后端 `/api/v1/gis/mushroom-risk?city=chengdu` 是否能直接返回
- 真机调试时地图组件需要 HTTPS 域名；本地仍可走 `localhost`

### Q6 拍照功能模拟器不可用

- 模拟器相机是 mock 数据，识别结果不可靠
- 必须真机预览才能验证完整链路

### Q7 后端返回 500 但小程序无日志

- 工具 → 详情 → 本地设置 → 勾选「启用客户端调试」
- 真机调试入口：右上角三个点 → 打开调试

## 9. 性能与体验调试

- **Audits 面板**（工具左下角）自动跑 Lighthouse-like 检查，可发现首屏过大、未启用按需注入等问题
- **Trace 面板**：录制 5 秒交互过程，导出 `trace.json` 用于性能分析
- `app.json` 已开启 `lazyCodeLoading: requiredComponents`，按需注入页面组件

## 10. 发布到正式环境（仅作概览，正式提审前需准备完整）

1. **公众平台配置**
   - 设置 → 基本设置：填写小程序名称、图标、类目（医疗 → 健康保健）
   - 开发 → 开发管理 → 服务器域名：填入后端 HTTPS 域名（必须是 ICP 备案过的）
   - 开发 → 开发管理 → 接口设置：勾选所需权限（位置、相机等）
2. **提交审核**
   - 工具右上角 → 上传 → 填写版本号与项目备注
   - 公众平台 → 版本管理 → 提交审核
   - 类目审核通常 1-3 个工作日
3. **发布**
   - 审核通过后 → 发布上线
   - 全网生效约 5-30 分钟
4. **备案与合规**
   - 上线前需完成 ICP 备案
   - 涉及健康数据的类目可能要求补充医疗相关资质

## 11. 进阶：CI/CD 与上传密钥

- **上传密钥**：公众平台 → 开发管理 → 上传代码密钥管理 → 生成 IP 白名单
- **miniprogram-ci**：可用 `miniprogram-ci upload` 在 CI 中自动上传，参考 <https://developers.weixin.qq.com/miniprogram/dev/devtools/ci.html>

## 12. 下一步

- 接入真实后端：参考 [deployment.md](./deployment.md)
- 申请 AppID / 类目：参考 [compliance.md](./compliance.md)
- API 详细约定：参考 [api.md](./api.md)
- 架构与数据流：参考 [architecture.md](./architecture.md)