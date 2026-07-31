"""FastAPI 应用入口
运行：python main.py
或：uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
"""
from app.main import app

if __name__ == "__main__":
    import uvicorn
    from app.config import settings

    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_env == "development",
        log_level=settings.log_level.lower(),
    )