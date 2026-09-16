# 部署指南

## 本地开发

### 后端

```bash
cd server
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python main.py
```

启动后访问 <http://localhost:8000/docs> 查看 Swagger 文档。

### 小程序

1. 打开「微信开发者工具」
2. 选择「导入项目」 → 目录指向 `miniprogram/`
3. AppID 暂用测试号即可
4. 详情 → 本地设置 → 勾选「不校验合法域名」

## 数据库初始化

```bash
cd server
python -m app.db.init_db
```

会建表并灌入演示知识库/GIS 数据。

## Docker 部署

```bash
cd server
docker compose up -d --build
```

`docker-compose.yml` 同时启动：

- `api`：FastAPI 服务（8000）
- `postgres`：数据库（5432）

生产前请：

1. 修改 `.env` 中 `JWT_SECRET` 为随机长串
2. 修改 PostgreSQL 默认账号密码
3. 关闭 `APP_ENV=development`
4. 配置 `WECHAT_APPID` 与 `WECHAT_SECRET`
5. 配置服务端 `QWEN_API_KEY` 与私有 COS 的 `MEDIA_COS_*` 参数

## 生产环境

正式环境首选微信云托管 / CloudBase，完整步骤见 [微信云托管上线手册](./deploy-wechat-cloudrun.md)。小程序代码由微信开发者工具上传，FastAPI 容器由云托管运行；Railway 和自建服务器仅作为联调或备选部署方式。

### 推荐架构

- 应用：CloudBase 云托管运行根目录 Dockerfile
- PostgreSQL：CloudBase PG 模式或同地域腾讯云 PostgreSQL，启用备份
- Redis：当前版本不需要；后续确需缓存或分布式锁时再通过 VPC 接入
- 文件：私有腾讯云 COS，不写入容器本地磁盘
- 小程序接入：首版使用云托管公网 HTTPS，完成上传链路改造后可切换 `wx.cloud.callContainer`
- 域名与备案：若绑定自定义域名，使用单位主体并按平台要求备案

### 监控告警

- 接口成功率与高分位延迟
- Qwen 调用量、失败率与费用
- 错误日志关键字告警（如 `INTERNAL_ERROR`），且日志不得记录密钥或健康原文

### 备份策略

- 在数据库控制台启用符合运营单位要求的备份策略，并实际验证恢复流程
- 私有 COS 根据数据保存规则配置版本控制或生命周期；不得改成公开读
- 备份周期与保留期限由运营单位确认后写入运维制度

### 上线 Checklist

- [ ] `.env` 已替换为生产密钥
- [ ] 已申请并配置微信小程序合法域名
- [ ] 已完成首次等保定级备案
- [ ] 已配置域名 SSL
- [ ] 已与甲方对齐验收口径
