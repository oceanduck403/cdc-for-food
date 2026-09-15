"""The production migration chain must recreate the current ORM schema."""
import os
import subprocess
import sys

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy.ext.asyncio import create_async_engine

from app.models import Base


async def test_alembic_head_matches_models(tmp_path):
    database = tmp_path / "migration.sqlite3"
    env = os.environ.copy()
    env.update(APP_ENV="development", DATABASE_URL=f"sqlite:///{database.as_posix()}")
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=os.path.dirname(os.path.dirname(__file__)),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr

    engine = create_async_engine(f"sqlite+aiosqlite:///{database.as_posix()}")
    try:
        async with engine.connect() as connection:
            differences = await connection.run_sync(
                lambda sync_connection: compare_metadata(
                    MigrationContext.configure(sync_connection), Base.metadata
                )
            )
        assert differences == []
    finally:
        await engine.dispose()
