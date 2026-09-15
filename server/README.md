# 营养健康 AI 小助手 · 后端服务（FastAPI）

提供微信小程序 API：用户档案、AI 识图膳食评估、个性化报告、知识库、毒蘑菇 GIS、管理后台，以及文章互动与站内消息。

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
- 限流键 `user:{id}:{day}`，由 Redis 实现每日分析次数闸口
- 商用菜品识别 API 通过 `vision_service.py` 抽象，便于切换供应商
- 文章列表、详情、点赞、收藏、评论、举报和站内消息位于 `/api/v1/community`；个人操作需登录，举报处理仅管理员可用。`alembic/versions/0002_community.py` 包含互动数据表迁移。
- 患者在 `/api/v1/users/me` 修改昵称；头像通过带登录令牌的 `POST /api/v1/users/me/avatar` 上传。服务端只接收 5 MB 以内的有效 JPG/PNG/WebP，裁成 512×512 JPEG 并清除原图元数据，文件位于 `uploads/avatars/`。Docker Compose 已挂载 `./uploads:/app/uploads`，部署时需保留该目录或迁移到对象存储；此入口只用于个人头像，不用于科普素材。

## 下一步

1. 落地 `app/db/init_db.py` 初始化脚本与 Alembic 迁移
2. 接入微信 code2Session、绑定手机号
3. 接入商用菜品识别 API（推荐先以 mock 数据演示）
4. 与甲方确认毒蘑菇 GIS 数据格式后接入 `gis/` 目录
