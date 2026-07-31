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
- `redis`：缓存（6379）

生产前请：

1. 修改 `.env` 中 `JWT_SECRET` 为随机长串
2. 修改 PostgreSQL 默认账号密码
3. 关闭 `APP_ENV=development`
4. 配置 `WECHAT_APPID` 与 `WECHAT_SECRET`
5. 配置 `OSS_*` 与 `VISION_*` 系列密钥

## 生产环境

### 推荐架构

- 应用服务器：2 核 4G 起，根据日活调整
- PostgreSQL：主从架构 + 每日备份
- Redis：单实例 + 持久化
- OSS：膳食图片与 GIS 静态资源
- HTTPS：Let's Encrypt / 阿里云 SSL
- 域名与备案：使用单位主体

### 监控告警

- 接口成功率、99 线延迟
- 视觉 API 调用量与费用
- 错误日志关键字告警（`INTERNAL_ERROR`、`VisionTimeout`）

### 备份策略

- PostgreSQL 每日凌晨全量 + binlog 增量
- OSS 启用版本控制（versioning）
- 每周异地冷备一份

### 上线 Checklist

- [ ] `.env` 已替换为生产密钥
- [ ] 已申请并配置微信小程序合法域名
- [ ] 已完成首次等保定级备案
- [ ] 已配置域名 SSL
- [ ] 已与甲方对齐验收口径