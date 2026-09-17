# 营养健康 AI 小助手 · 后端服务（FastAPI）

提供微信小程序 API：用户档案、Qwen 膳食分析与健康科普、个性化报告、知识库、健康评估、医生指导、管理后台，以及文章互动与站内消息。

## 目录结构

```
server/
├── main.py                    uvicorn 入口（直接 python main.py 即可）
├── requirements.txt           依赖
├── .env.example               环境变量模板
├── Dockerfile / docker-compose.yml
├── app/
│   ├── core/                  配置 / 安全 / 日志 / 异常
│   ├── api/v1/                REST 路由
│   ├── models/                SQLAlchemy ORM
│   ├── schemas/               Pydantic 数据模型
│   ├── services/              业务逻辑
│   └── db/                    数据库会话
└── tests/                     pytest 测试
```

## 启动

```bash
cd server
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python main.py
# 或 uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

接口文档：<http://localhost:8000/docs>

## 关键约定

- 所有路由挂载在 `/api/v1`
- 鉴权使用 JWT（`Authorization: Bearer <token>`）
- AI 调用次数写入 PostgreSQL `ai_usage_events`，同一事务完成预占与失败回滚，当前不依赖 Redis
- 食物图片由 `/api/v1/ai/food-analysis` 发往服务端 Qwen 网关；AI Key 不下发到小程序
- 文章列表、详情、点赞、收藏、评论、举报和站内消息位于 `/api/v1/community`；个人操作需登录，举报处理仅管理员可用。`alembic/versions/0002_community.py` 包含互动数据表迁移。
- 患者在 `/api/v1/users/me` 修改昵称；头像通过带登录令牌的 `POST /api/v1/users/me/avatar` 上传。服务端校验并重编码图片、调用微信内容安全检测，生产环境保存到私有 COS 或 PG 环境内置 CloudBase 云存储，并以短期签名的后端代理地址访问。此入口只用于个人头像，不用于科普素材。

## 下一步

1. 复制 `.env.example` 并填写本地配置；不要提交 `.env`
2. 执行 `alembic upgrade head`，再运行服务
3. 生产部署按 `../docs/deploy-wechat-cloudrun.md` 配置 PostgreSQL、私有 CloudBase 云存储（或 COS）和服务端密钥
