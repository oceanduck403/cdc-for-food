"""The production migration chain must recreate the current ORM schema."""
import os
import sqlite3
import subprocess
import sys

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy.ext.asyncio import create_async_engine

from app.models import Base


def test_original_survey_migration_freezes_old_questions_before_catalog_restore(tmp_path):
    database = tmp_path / "historical-survey.sqlite3"
    env = os.environ.copy()
    env.update(APP_ENV="development", DATABASE_URL=f"sqlite:///{database.as_posix()}")

    def migrate(revision):
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", revision],
            cwd=os.path.dirname(os.path.dirname(__file__)), env=env,
            capture_output=True, text=True, check=False,
        )
        assert result.returncode == 0, result.stderr

    migrate("0005_ai_usage_events")
    old_questions = '[{"id":"old_question","title":"旧模板题目"}]'
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO users (id,role,nickname,is_active,created_at,updated_at) "
            "VALUES (1,'patient','历史用户',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
        )
        connection.execute(
            "INSERT INTO survey_templates "
            "(id,type,name,description,questions,category,is_active,sort_order,created_at,updated_at) "
            "VALUES (1,'weight_clinic_first','旧首诊表','',?,'体重管理',0,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)",
            (old_questions,),
        )
        connection.execute(
            "INSERT INTO survey_responses "
            "(id,template_id,user_id,template_type,user_name,user_phone,submitted_at,total_score,analysis,answers,created_at,updated_at) "
            "VALUES (1,1,1,'weight_clinic_first','','','旧日期',0,'','{}',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
        )

    migrate("head")
    with sqlite3.connect(database) as connection:
        snapshot, score = connection.execute(
            "SELECT questions_snapshot,total_score FROM survey_responses WHERE id=1"
        ).fetchone()
        assert snapshot == old_questions
        assert score == 0  # Historical stored values are not rewritten.
        assert connection.execute("SELECT catalog_revision FROM survey_templates WHERE id=1").fetchone() == (0,)
        connection.execute("UPDATE survey_responses SET total_score=NULL WHERE id=1")
        assert connection.execute("SELECT total_score FROM survey_responses WHERE id=1").fetchone() == (None,)


@pytest.mark.asyncio
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
