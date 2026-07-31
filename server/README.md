# 营养健康 AI 小助手 · 后端服务（FastAPI）

提供微信小程序所需的全部 API：用户档案、AI 识图膳食评估、个性化报告、知识库、毒蘑菇 GIS、管理后台等。

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

## 下一步

1. 落地 `app/db/init_db.py` 初始化脚本与 Alembic 迁移
2. 接入微信 code2Session、绑定手机号
3. 接入商用菜品识别 API（推荐先以 mock 数据演示）
4. 与甲方确认毒蘑菇 GIS 数据格式后接入 `gis/` 目录