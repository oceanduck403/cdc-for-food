# 微信云托管发布说明

本项目的小程序前端通过微信开发者工具上传；FastAPI 后端可以部署到微信云托管，不依赖 Railway。仓库根目录的 `Dockerfile` 可直接作为云托管构建入口。

## 当前账号状态

2026-09-15 通过小程序 AppID 的只读接口检查，返回 `no cloud base privilege`，说明这个小程序尚未开通云开发环境。需要先由小程序管理员在微信云开发控制台创建环境，再创建云托管服务。

## 建议资源

- 一个微信云开发环境，地域优先选择上海或广州。
- 一个云托管服务，例如 `nutrition-api`，构建上下文为仓库根目录，Dockerfile 路径为 `Dockerfile`。
- 一个 PostgreSQL 数据库和一个 Redis 实例。
- 私有云存储，用于头像与健康咨询图片；健康图片不能放在匿名可访问的静态目录。

## 生产环境变量

```text
APP_ENV=production
JWT_SECRET=<至少 32 位随机值>
DATABASE_URL=<PostgreSQL 连接地址>
REDIS_URL=<Redis 连接地址>
WECHAT_APPID=<小程序 AppID>
WECHAT_SECRET=<小程序 AppSecret>
QWEN_API_KEY=<轮换后的百炼 Key>
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
QWEN_MODEL=qwen-vl-plus
ADMIN_BOOTSTRAP_USERNAME=<首次管理员账号>
ADMIN_BOOTSTRAP_PASSWORD=<12 至 72 字节、含大小写/数字/符号的强密码>
```

容器启动时先执行 `alembic upgrade head`，再创建首个管理员并启动 API。管理员首次登录并修改密码后，应删除两项 `ADMIN_BOOTSTRAP_*` 环境变量。

## 前端接入

服务创建后可以使用云托管公网 HTTPS 地址，将其填入 `miniprogram/utils/config.js` 的 `apiBase` 并登记为合法域名；也可以改用 `wx.cloud.callContainer` 走微信内部链路。后者还要填写真实环境 ID 和服务名，并适配头像、聊天图片上传。

在环境和服务尚未创建前，不应把示例域名写入正式包。
