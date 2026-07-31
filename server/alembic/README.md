# Alembic 迁移说明

## 一次性初始化

```bash
cd server
alembic init alembic
# 编辑 alembic/env.py 引入 app.config 与 app.models
alembic revision --autogenerate -m "init schema"
alembic upgrade head
```

环境会自动检测 `DATABASE_URL`，切换 SQLite 与 PostgreSQL。

## 已支持的数据库

| 场景 | DATABASE_URL 示例 |
| --- | --- |
| 本地开发 | `sqlite:///./data/app.db` |
| 生产 PostgreSQL | `postgresql+asyncpg://user:pass@host:5432/nutrition` |

## 常用命令

```bash
alembic current                  # 当前版本
alembic history                  # 历史
alembic upgrade head             # 升级到最新
alembic downgrade -1             # 回退一个版本
alembic revision -m "add idx"    # 手写迁移
alembic revision --autogenerate -m "auto"  # 自动生成
```

## 与旧 `init_db()` 的关系

- 旧 `init_db()` 通过 `Base.metadata.create_all` 建表，仅开发期使用
- 生产强制使用 Alembic
- 首次切换到 PostgreSQL 时，先 `alembic stamp head` 标记当前 schema 为最新

## 已生成的迁移

参见 `server/alembic/versions/`。