# 微信云托管 / CloudBase 上线手册

## 结论

本项目不要求使用 Railway。小程序前端仍由微信开发者工具上传到微信公众平台，FastAPI 后端部署到微信云托管（CloudBase 云托管）。微信公众平台负责代码包、体验版、审核和发布，不能直接运行 FastAPI、PostgreSQL 或 Redis；云托管才是微信生态中承载后端容器的服务。

Railway 只保留为临时联调或灾备选项。正式环境优先采用：

```text
微信小程序
  └─ wx.cloud.callContainer（正式版私有链路）
       └─ CloudBase 云托管：FastAPI 容器
            ├─ PostgreSQL
            ├─ CloudBase 云存储 / COS
            ├─ 微信开放接口
            └─ 阿里云百炼接口
```

## 当前状态与不可代填项

截至 2026-09-17，已创建 CloudBase PG 环境 `cdc-food-prod-d8gtxkdw22781847c`，云托管服务名确定为 `cdc-food-api`，小程序生产配置已经写入这两个非敏感标识。当前仍需在控制台完成服务端资源和密钥配置。

当前还没有以下真实值，仓库中不得写假值：

- PostgreSQL 的连接地址、账号和密码
- CloudBase 服务端 `service_role` API Key
- 已轮换且未泄漏的百炼 API Key

## 资源选型

### FastAPI 容器

仓库根目录的 `Dockerfile` 可直接用于云托管源码构建：

- 构建上下文：仓库根目录
- Dockerfile：`Dockerfile`
- 服务端口：`8000`
- 监听地址：`0.0.0.0`
- 启动命令：先执行 Alembic 迁移，再引导首个管理员，最后启动 Uvicorn
- 进程健康地址：`GET /health`

云托管会在容器内注入 `PORT`。Dockerfile 已使用 `${PORT:-8000}`，所以不要在环境变量中手工固定 `PORT`；控制台填写的服务端口要与容器实际端口一致。发布后用服务默认域名访问 `/health`，应返回 `status: ok`。

首次发布先设为 1 个实例，确认数据库迁移完成后再调整扩缩容，避免新库初始化时多个实例同时执行 DDL。

### PostgreSQL

当前代码、Alembic 迁移和生产配置使用 PostgreSQL + `asyncpg`，不需要改业务代码。连接串支持以下前缀；应用会把前两种自动转换为异步驱动格式：

```text
postgres://...
postgresql://...
postgresql+asyncpg://...
```

有两条可行路径：

1. 在腾讯云 CloudBase 控制台新建 **PG 模式环境**，从数据库控制台取得服务端直连地址。CloudBase 官方文档明确支持云托管通过 PostgreSQL 协议直连。微信云开发控制台目前不能创建 PG 模式环境，因此这一条必须从腾讯云 CloudBase 控制台创建，再按控制台能力关联小程序。
2. 开通普通微信云托管环境，同时创建同地域的腾讯云 PostgreSQL，通过云托管的 VPC 私有网络访问。这条路径也不需要修改代码。

不要为了使用云托管内置 MySQL，直接把 `DATABASE_URL` 改成 MySQL。当前依赖中没有异步 MySQL 驱动，生产校验也只接受 PostgreSQL，迁移链尚未在 MySQL 上验证。若以后确定迁到 MySQL，需要单独完成驱动、迁移和全量回归。

连接数据库时使用控制台显示的真实地址、端口和 SSL 要求。账号密码中如含 `@`、`:`、`/` 等字符，要按 URL 规则编码。

### Redis

当前版本的 AI 调用限额已经记录在 PostgreSQL 的 `ai_usage_events` 表中，生产环境**不需要额外购买 Redis**，环境变量中也不需要 `REDIS_URL`。这是目前资源最少的部署路径。

如果后续因高并发、缓存或分布式锁重新引入 Redis，云托管可以通过 VPC 访问同地域的腾讯云 Redis。届时使用内网连接串，并只给云托管所在子网放行：

```text
redis://:<密码>@<内网地址>:6379/0
```

若控制台要求 TLS，则使用它给出的 `rediss://` 地址。安全组或访问控制只放行云托管所在子网。

### 出网与文件存储

服务需要访问 `api.weixin.qq.com` 和 `dashscope.aliyuncs.com`。绑定 VPC 后必须验证这两个 HTTPS 出站请求；若关闭平台默认公网出口，应给子网配置 NAT 网关和路由。

云托管实例会被重建和水平扩容，不能把用户头像、咨询图片或数据库文件永久保存在容器目录。PG 环境优先使用内置 CloudBase 云存储：设置 `MEDIA_STORAGE_BACKEND=cloudbase_pg`，在环境的“API 密钥”页创建服务端 API Key，并建立私有 `user-media` Bucket。这个 Key 仅限当前 CloudBase 环境，不需要创建账号级 CAM AccessKey；它属于 `service_role`，必须只放在云托管环境变量中。上传图片经校验、内容安全检测和重编码后写入随机对象键，数据库只保存不透明引用，小程序仍通过后端短期签名代理读取。

如使用独立 COS，也可保留 `MEDIA_STORAGE_BACKEND=cos` 和 `MEDIA_COS_*` 配置。两种生产后端都禁止公开读，本地目录仅用于开发和测试。PG 内置云存储所需变量为：

```text
MEDIA_STORAGE_BACKEND=cloudbase_pg
MEDIA_CLOUDBASE_ENV_ID=<环境 ID>
MEDIA_CLOUDBASE_API_KEY=<服务端 API Key；仅放后端>
MEDIA_CLOUDBASE_BUCKET=user-media
MEDIA_CLOUDBASE_TIMEOUT_SECONDS=15
MEDIA_COS_PREFIX=private/user-media
```

## 创建环境和服务

1. 用与小程序主体一致的管理员账号进入 CloudBase 控制台，创建或关联环境。
2. 如果选 CloudBase 自带 PostgreSQL，创建新环境时选择 PG 模式；该模式只支持新环境，存量传统环境不能原地切换。
3. 创建云托管服务。服务名按真实名称填写并记录，后续不能修改。
4. 选择从 Git 仓库或本地源码部署，目录选仓库根目录，Dockerfile 名称填 `Dockerfile`，服务端口填 `8000`。
5. 配置 PostgreSQL 所在网络及访问规则；当前版本不需要 Redis。
6. 在“服务设置 → 环境变量”中以 JSON 或 Key-Value 方式录入生产变量。可复制 `deploy/cloudbase/environment.example.json`，替换全部 `__FILL_...__` 后粘贴；填好的文件不得提交 Git。
7. 初次发布将实例数设为 1，查看构建和启动日志，确认 Alembic 到最新版本。
8. 访问 `https://<控制台给出的真实域名>/health`，再测试登录、问卷、AI 和图片链路。
9. 管理员首次登录并修改密码后，从服务环境变量中删除 `ADMIN_BOOTSTRAP_USERNAME` 和 `ADMIN_BOOTSTRAP_PASSWORD`，重新发布版本。

可在提交前做不泄露密钥的静态校验：

```powershell
python deploy/cloudbase/validate_config.py deploy/cloudbase/environment.local.json
```

校验器只报告字段问题，不打印字段值。

## 小程序接入方式

正式版已经统一使用 `wx.cloud.callContainer`。它走微信到云托管的专用链路，不消耗公网流量，也不需要在公众平台配置普通 `request`、`uploadFile` 或 `downloadFile` 合法域名：

```javascript
wx.cloud.init({ env: 'cdc-food-prod-d8gtxkdw22781847c' });

wx.cloud.callContainer({
  config: { env: 'cdc-food-prod-d8gtxkdw22781847c' },
  path: '/health',
  method: 'GET',
  header: {
    'X-WX-SERVICE': 'cdc-food-api'
  }
});
```

`miniprogram/utils/transport.js` 已统一处理普通 JSON 请求、multipart 图片上传和私有图片下载缓存。体验版必须真机回归登录、头像、咨询图片及图片预览。开发版需要本地后端时，可通过 `__cdc_api_transport__` 与 `__cdc_api_base__` 两个本机存储项临时切换直连；体验版和正式版不会读取这个覆盖配置。

## 发布验收

- `GET /health` 返回 200，且 `env` 为 `production`
- 启动日志中 Alembic 成功到达最新 revision，没有数据库或 Redis 地址泄露
- PostgreSQL 使用非本机地址，容器重启后数据仍在
- 微信登录调用真实 `jscode2session`，生产环境不会回退 mock
- 百炼 Key 已轮换，只存在服务端环境变量
- 真机完成登录、健康评估、打卡、科普互动、AI 问答、头像和咨询图片全链路
- 容器扩缩容或重启后用户数据和图片仍可访问
- 小程序正式包中没有局域网 IP、示例域名、环境占位符或测试账号

## 官方依据

- [CloudBase 云托管概述：支持 FastAPI、Docker、Git 部署，并可连接 PostgreSQL / Redis](https://docs.cloudbase.net/run/introduction)
- [从源代码部署：Dockerfile、真实端口和默认域名验证](https://docs.cloudbase.net/run/deploy/deploy/deploying-source-code)
- [服务开发说明：监听 `PORT`、绑定 `0.0.0.0`、无状态要求](https://docs.cloudbase.net/run/develop/developing-guide)
- [小程序调用云托管：`wx.cloud.callContainer`、环境 ID 与服务名](https://docs.cloudbase.net/run/develop/access/mini)
- [服务设置：公网 HTTPS、环境变量和服务名约束](https://docs.cloudbase.net/run/deploy/service-setting)
- [CloudBase PostgreSQL 连接：云托管可用 PostgreSQL 协议直连](https://docs.cloudbase.net/database/postgresql/connecting-to-postgresql)
- [云开发环境模式：微信云开发暂不能创建 PG 模式环境](https://docs.cloudbase.net/quick-start/env-overview)
- [VPC 配置：访问 PostgreSQL、Redis 及公网出站要求](https://docs.cloudbase.net/run/deploy/networking/vpc)
- [迁移既有服务：容器必须无状态，文件应放对象存储](https://docs.cloudbase.net/run/best-practice/migration)
