# 生产环境部署手册

> 目标：把 `server/` 部署到一台腾讯云轻量应用服务器，通过 Nginx + HTTPS 对外提供 API 服务。

## 0. 总览

```
用户微信小程序
    ↓ HTTPS
CDN / 域名（api.cdcdc-health.cn，已 ICP 备案）
    ↓
Nginx（监听 443，转发到 127.0.0.1:8000）
    ↓
FastAPI（uvicorn / gunicorn）
    ↓                    ↓
PostgreSQL             Redis
    ↓
对象存储 COS（膳食图片）
    ↓
商用菜品识别 API
```

## 1. 购买云资源（建议配置）

### 1.1 腾讯云轻量应用服务器

| 项 | 配置 |
| --- | --- |
| 套餐 | 通用型 2C4G / 80G SSD / 4M 带宽 |
| 系统 | Ubuntu 22.04 LTS |
| 地域 | 成都（ap-chengdu） |
| 月费 | 约 ¥80 |

**为什么不上 CVM**：轻量更便宜、对小程序 / Web 流量足够。

### 1.2 腾讯云 PostgreSQL（可选）

| 项 | 配置 |
| --- | --- |
| 规格 | 1C2G / 25G SSD |
| 月费 | 约 ¥60 |

**或者**：在轻量服务器里用 Docker 自建 PostgreSQL（节省成本但需要自己备份）。

### 1.3 腾讯云 COS

- 存储桶：与服务器同地域（ap-chengdu）
- 访问权限：私有读写 + CDN 回源
- 计费：50GB 存储 + 100GB 流量 = 约 ¥10/月

### 1.4 域名 + SSL

- 域名：`api.cdcdc-health.cn`
- SSL：腾讯云免费 DV 证书

## 2. 服务器初始化

```bash
# 登录服务器
ssh ubuntu@<your-server-ip>

# 创建非 root 用户
sudo adduser nutrition
sudo usermod -aG sudo nutrition
sudo su - nutrition

# 基础工具
sudo apt update && sudo apt install -y git curl wget vim ufw software-properties-common
```

### 2.1 防火墙

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp     # SSH
sudo ufw allow 80/tcp     # HTTP（用于 certbot 验证）
sudo ufw allow 443/tcp    # HTTPS
sudo ufw enable
```

### 2.2 安装 Docker（用于 Redis / PostgreSQL）

```bash
# 官方脚本（推荐）
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker nutrition
newgrp docker
docker --version
```

### 2.3 安装 Docker Compose

```bash
sudo apt install -y docker-compose-plugin
docker compose version
```

## 3. 部署 PostgreSQL + Redis（Docker）

创建 `/home/nutrition/data-stack/docker-compose.yml`：

```yaml
version: "3.9"

services:
  postgres:
    image: postgres:16-alpine
    container_name: nutrition-postgres
    restart: unless-stopped
    environment:
      POSTGRES_USER: nutrition
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: nutrition
    volumes:
      - /home/nutrition/data-stack/pgdata:/var/lib/postgresql/data
      - ./backups:/backups
    ports:
      - "127.0.0.1:5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U nutrition"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: nutrition-redis
    restart: unless-stopped
    command: redis-server --requirepass ${REDIS_PASSWORD}
    volumes:
      - /home/nutrition/data-stack/redisdata:/data
    ports:
      - "127.0.0.1:6379:6379"
```

创建 `.env`：

```bash
POSTGRES_PASSWORD=<强随机密码>
REDIS_PASSWORD=<强随机密码>
```

启动：

```bash
cd /home/nutrition/data-stack
docker compose up -d
docker compose ps
```

## 4. 部署 FastAPI（systemd）

### 4.1 拉取代码

```bash
sudo mkdir -p /opt/nutrition
sudo chown nutrition:nutrition /opt/nutrition
cd /opt/nutrition
git clone https://github.com/your-org/cdcdc-nutrition.git server
cd server
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install gunicorn
```

### 4.2 配置 .env（生产密钥）

```bash
cp .env.example .env
vim .env
```

**关键字段**（必须替换）：

```bash
APP_ENV=production
JWT_SECRET=<openssl rand -hex 32>      # 生成强随机密钥
DATABASE_URL=postgresql+asyncpg://nutrition:<password>@localhost:5432/nutrition
REDIS_URL=redis://:<password>@localhost:6379/0

WECHAT_APPID=wx替换成真实AppID
WECHAT_SECRET=<真实AppSecret>

VISION_PROVIDER=baidu
VISION_API_KEY=<百度API Key>
VISION_API_SECRET=<百度Secret Key>

OSS_BUCKET=nutrition-ai
OSS_ACCESS_KEY=<腾讯云SecretId>
OSS_SECRET_KEY=<腾讯云SecretKey>
OSS_ENDPOINT=cos.ap-chengdu.myqcloud.com

DAILY_ANALYSIS_LIMIT_PER_USER=20
IMAGE_MAX_BYTES=2097152
```

### 4.3 数据库迁移

```bash
cd /opt/nutrition/server
source .venv/bin/activate
alembic upgrade head
python -m app.db.init_db     # 灌入演示数据
```

### 4.4 创建 systemd 单元

`/etc/systemd/system/nutrition-api.service`：

```ini
[Unit]
Description=Nutrition AI FastAPI
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=nutrition
WorkingDirectory=/opt/nutrition/server
Environment="PATH=/opt/nutrition/server/.venv/bin"
ExecStart=/opt/nutrition/server/.venv/bin/gunicorn app.main:app \
    -k uvicorn.workers.UvicornWorker \
    -b 127.0.0.1:8000 \
    -w 2 \
    --timeout 60 \
    --access-logfile /var/log/nutrition/access.log \
    --error-logfile /var/log/nutrition/error.log
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

启用：

```bash
sudo mkdir -p /var/log/nutrition
sudo chown nutrition:nutrition /var/log/nutrition
sudo systemctl daemon-reload
sudo systemctl enable nutrition-api
sudo systemctl start nutrition-api
sudo systemctl status nutrition-api
```

### 4.5 健康检查

```bash
curl http://127.0.0.1:8000/docs      # Swagger UI
curl http://127.0.0.1:8000/api/v1/auth/health
```

## 5. 部署 Nginx + HTTPS

### 5.1 安装 Nginx

```bash
sudo apt install -y nginx
```

### 5.2 上传 SSL 证书

从腾讯云 SSL 控制台下载证书：

```bash
sudo mkdir -p /etc/nginx/ssl
sudo cp /tmp/api.cdcdc-health.cn_bundle.crt /etc/nginx/ssl/
sudo cp /tmp/api.cdcdc-health.cn.key /etc/nginx/ssl/
sudo chmod 600 /etc/nginx/ssl/*
```

### 5.3 站点配置

`/etc/nginx/sites-available/nutrition-api.conf`：

```nginx
upstream nutrition_backend {
    server 127.0.0.1:8000;
    keepalive 32;
}

server {
    listen 80;
    server_name api.cdcdc-health.cn;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.cdcdc-health.cn;

    ssl_certificate     /etc/nginx/ssl/api.cdcdc-health.cn_bundle.crt;
    ssl_certificate_key /etc/nginx/ssl/api.cdcdc-health.cn.key;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 1d;

    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;

    client_max_body_size 5M;

    location / {
        proxy_pass http://nutrition_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_read_timeout 60s;
    }
}
```

启用：

```bash
sudo ln -s /etc/nginx/sites-available/nutrition-api.conf /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 5.4 验证

```bash
curl -I https://api.cdcdc-health.cn/docs
```

## 6. 配置小程序后台

微信小程序后台 → 开发 → 开发管理：

| 项 | 值 |
| --- | --- |
| request 合法域名 | `https://api.cdcdc-health.cn` |
| uploadFile 合法域名 | `https://nutrition-ai.cos.ap-chengdu.myqcloud.com` |
| downloadFile 合法域名 | 同上 |
| 开发者微信号 | 你的微信 |

## 7. 监控与备份

### 7.1 数据库备份（每日 cron）

```bash
mkdir -p /home/nutrition/data-stack/backups
cat > /home/nutrition/backup.sh <<'EOF'
#!/bin/bash
TS=$(date +%Y%m%d_%H%M%S)
docker exec nutrition-postgres pg_dump -U nutrition nutrition | \
    gzip > /home/nutrition/data-stack/backups/db_${TS}.sql.gz
# 保留 30 天
find /home/nutrition/data-stack/backups -mtime +30 -delete
EOF
chmod +x /home/nutrition/backup.sh
(crontab -l 2>/dev/null; echo "0 3 * * * /home/nutrition/backup.sh") | crontab -
```

### 7.2 日志收集

- 访问日志：`/var/log/nutrition/access.log`
- 错误日志：`/var/log/nutrition/error.log`
- Nginx 日志：`/var/log/nginx/`

### 7.3 进程守护

- systemd 自动拉起 FastAPI
- Docker 自动重启 PostgreSQL / Redis

### 7.4 监控告警（可选）

- 腾讯云「云监控」基础免费
- 配置：CPU > 80% 持续 5 分钟告警
- 短信 / 邮件告警渠道

## 8. 故障排查清单

| 症状 | 排查 |
| --- | --- |
| `502 Bad Gateway` | `systemctl status nutrition-api`，看后端是否启动 |
| 数据库连接失败 | `docker compose ps`，看 PostgreSQL 是否健康 |
| 接口超时 | `journalctl -u nutrition-api -n 50`，查错误日志 |
| Nginx 502 | `nginx -t` 检查配置；`systemctl reload nginx` |
| 微信登录 502 | `curl -v https://api.weixin.qq.com/sns/jscode2session?...` 检查外网 |
| 菜品识别失败 | 查 VISION_API_KEY / VISION_API_SECRET 是否正确 |

## 9. 升级流程

```bash
cd /opt/nutrition/server
git pull origin main
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
sudo systemctl restart nutrition-api
sudo systemctl status nutrition-api
```

## 10. 成本核算（按 ¥/月）

| 资源 | 费用 |
| --- | --- |
| 轻量服务器 2C4G | ¥80 |
| COS 50G | ¥10 |
| 域名 | ¥6（年付分摊） |
| SSL 证书 | ¥0（免费 DV） |
| 百度菜品识别（预估 1 万次） | ¥100 |
| **合计** | **约 ¥200/月** |

## 11. 安全清单

- [x] HTTPS + HSTS
- [x] 数据库不在公网监听
- [x] .env 文件不在 git 中
- [x] JWT secret 用 `openssl rand -hex 32`
- [x] 接口限流（基于 Redis）
- [x] 图片大小限制（5M）
- [x] 操作日志留存 6 个月
- [x] 防火墙仅放行 22/80/443
- [x] 数据库每日备份 + 30 天保留

## 12. 后续优化（视用户量决定）

- HTTPS + 自定义域名 CDN（按量计费）
- 多副本 + 负载均衡（用户 > 1 万时）
- Sentry 错误追踪
- Prometheus + Grafana 监控面板
- 等保 2.0 二级测评（合规要求时）

---

**下一步**：完成上述步骤后，按 [go-live-checklist.md](./go-live-checklist.md) 中的「提交审核」流程上线小程序。