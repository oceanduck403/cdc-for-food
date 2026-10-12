# 电脑本地预览手册

更新日期：2026-10-12。当前目标是电脑微信开发者工具试运行，不上传、提审或部署。完整配置和边界见 [技术交接说明](technical-handoff.md)。

## 1. 启动独立后端

准备 Python 3.12、Node.js 和微信开发者工具。在仓库根目录执行：

```powershell
py -3.12 -m venv server/.venv
server/.venv/Scripts/python.exe -m pip install -r server/requirements.txt
if (-not (Test-Path -LiteralPath 'server/.env')) {
    Copy-Item server/.env.example server/.env
}
```

仅首次复制 `.env`，不要覆盖已有配置。在该文件安全填写微信 AppID/AppSecret 与千问 Key。随后：

```powershell
server/.venv/Scripts/python.exe deploy/selfhost/run_local_demo.py
```

默认独立运行目录为 `%LOCALAPPDATA%/CDC-Food/local-demo`，端口 `18121`，API 前缀 **`/api/v1`**。启动器先迁移数据库、首次插入原始五表和开发参考内容，并默认关闭医生服务；不连接生产数据库，不自动创建管理员。

该启动器固定北京兼容接口与 `qwen3.8-27b`。模型或管理员的其他配置方式见交接说明；不能仅修改 `.env` 的模型变量后假定启动器会采用它。

## 2. 导入并配置小程序

1. 在微信开发者工具导入**仓库根目录**，不要误将根 `app/` 当成前端；`project.config.json` 指定 `miniprogramRoot: miniprogram/`。
2. 使用项目方授权的开发者身份。真实微信登录要求 AppID 与服务端配置一致；测试号不能验证真实用户身份链路。
3. 仅电脑本地联调时，在工具「详情 → 本地设置」按需勾选「不校验合法域名、web-view（业务域名）、TLS 版本以及 HTTPS 证书」。此设置不适用于体验版/正式版。
4. 在小程序调试控制台执行以下开发版配置：

```javascript
wx.setStorageSync('__cdc_api_transport__', 'direct')
wx.setStorageSync('__cdc_api_base__', 'http://127.0.0.1:18121/api/v1')
```

5. 重新编译并登录。不要直接把开发地址写入源码的 `release-runtime.js`。

## 3. 验证顺序

- 健康评估：确认 5 套原始表、分页、零食条件跳题、24 小时时间和小数输入；原稿未给评分规则，不显示虚构分数。
- 打卡：膳食/运动/饮水记录、进度与七日足迹。
- AI：文字输入、快捷问题和真实回复；需要联网及有效模型 Key。
- 科普：文章、点赞/收藏/评论、消息和收藏列表。
- 我的：头像/昵称和资料、隐私条款及账号操作入口。

管理员账号需在独立测试环境显式引导，不能使用固定默认口令。相机、真实图片模型、平台审核与全部机型表现需要另行验证。

## 4. 常见问题与环境区别

| 现象 | 检查事项 |
| --- | --- |
| 问卷或接口无法加载 | `/health` 是否返回正常、端口/API 前缀是否一致、当前是否开发版、是否设置本机覆盖 |
| AI 无回复 | 服务端 Key/地域/模型是否匹配、网络、配额和服务日志；不要在日志中打印凭据 |
| 切换环境后返回 401 | 退出旧会话后重新登录；不要为了清 token 删除全部本地打卡/草稿 |
| 本地端口已占用 | 启动器只复用确认属于自身的实例；不会关闭未知服务 |
| 手机不能连接 | `127.0.0.1` 在手机上指手机自身；真机需另行准备可访问地址，本演示启动器只监听电脑回环地址 |
| 体验版忽略本机设置 | 属于预期行为：开发覆盖仅在 `envVersion=develop` 生效，体验/正式使用构建注入的 HTTPS 地址 |

`build/` 是本地生成产物，不随 Git 交接。正式构建与校验见 [构建手册](../deploy/selfhost/README.md)，本手册不执行上传或发布。
