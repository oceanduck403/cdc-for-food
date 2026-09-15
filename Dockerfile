FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY server/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY server/app ./app
COPY server/alembic ./alembic
COPY server/alembic.ini ./alembic.ini

RUN mkdir -p /app/data /app/logs /app/uploads

EXPOSE 8000

# 生产表结构由 Alembic 管理；随后只引导首个强密码管理员。
# PORT 由托管平台注入，本地容器默认使用 8000。
CMD ["sh", "-c", "alembic upgrade head && python -m app.db.init_db && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
