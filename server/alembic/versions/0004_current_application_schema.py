"""Bring the legacy database up to the schema used by the application.

Revision ID: 0004_current_application_schema
Revises: 0003_admin_token_version
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004_current_application_schema"
down_revision: Union[str, None] = "0003_admin_token_version"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    ]


def _assert_unique_nullable_value(table: str, column: str) -> None:
    duplicate = op.get_bind().execute(
        sa.text(
            f"SELECT {column} FROM {table} "
            f"WHERE {column} IS NOT NULL GROUP BY {column} "
            f"HAVING COUNT(*) > 1 LIMIT 1"
        )
    ).first()
    if duplicate:
        raise RuntimeError(
            f"cannot create unique index for {table}.{column}: duplicate values exist"
        )


def _assert_max_length(table: str, column: str, maximum: int) -> None:
    oversized = op.get_bind().execute(
        sa.text(
            f"SELECT 1 FROM {table} WHERE length({column}) > :maximum LIMIT 1"
        ),
        {"maximum": maximum},
    ).first()
    if oversized:
        raise RuntimeError(
            f"cannot reduce {table}.{column} to {maximum} characters: oversized values exist"
        )


def upgrade() -> None:
    # The first migration only represented WeChat patients.  The current user
    # table also stores doctors and administrators, so openid must be nullable.
    op.add_column(
        "users",
        sa.Column("role", sa.String(16), nullable=False, server_default="patient"),
    )
    op.add_column("users", sa.Column("username", sa.String(64), nullable=True))
    op.add_column("users", sa.Column("password_hash", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("real_name", sa.String(64), nullable=True))
    op.add_column("users", sa.Column("department", sa.String(64), nullable=True))
    op.add_column("users", sa.Column("title", sa.String(64), nullable=True))
    op.add_column("users", sa.Column("intro", sa.Text(), nullable=True))
    op.add_column(
        "users",
        sa.Column("is_available", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "users",
        sa.Column("is_vip", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("users", sa.Column("vip_expire_at", sa.Date(), nullable=True))
    op.add_column(
        "users",
        sa.Column("total_analysis_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "users",
        sa.Column(
            "purchased_analysis_count", sa.Integer(), nullable=False, server_default="0"
        ),
    )
    op.add_column(
        "users",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.execute(
        sa.text(
            "UPDATE users SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL"
        )
    )
    op.execute(
        sa.text(
            "UPDATE users SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL"
        )
    )
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "openid", existing_type=sa.String(64), existing_nullable=False, nullable=True
        )
        batch_op.alter_column(
            "created_at",
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=True,
            nullable=False,
        )
        batch_op.alter_column(
            "updated_at",
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=True,
            nullable=False,
        )
    _assert_unique_nullable_value("users", "phone")
    _assert_unique_nullable_value("users", "username")
    op.create_index("ix_users_phone", "users", ["phone"], unique=True)
    op.create_index("ix_users_role", "users", ["role"], unique=False)
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    op.add_column(
        "knowledge_articles",
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE knowledge_articles SET content_html = '' WHERE content_html IS NULL"
        )
    )
    op.execute(
        sa.text("UPDATE knowledge_articles SET version = 1 WHERE version IS NULL")
    )
    op.execute(
        sa.text(
            "UPDATE knowledge_articles SET created_at = CURRENT_TIMESTAMP "
            "WHERE created_at IS NULL"
        )
    )
    op.execute(
        sa.text(
            "UPDATE knowledge_articles SET updated_at = CURRENT_TIMESTAMP "
            "WHERE updated_at IS NULL"
        )
    )
    _assert_max_length("knowledge_articles", "source", 128)
    with op.batch_alter_table("knowledge_articles") as batch_op:
        batch_op.alter_column(
            "title", existing_type=sa.String(200), type_=sa.String(256), nullable=False
        )
        batch_op.alter_column(
            "summary", existing_type=sa.String(500), type_=sa.String(512), nullable=True
        )
        batch_op.alter_column(
            "content_html", existing_type=sa.Text(), existing_nullable=True, nullable=False
        )
        batch_op.alter_column(
            "source", existing_type=sa.String(200), type_=sa.String(128), nullable=True
        )
        batch_op.alter_column(
            "version", existing_type=sa.Integer(), existing_nullable=True, nullable=False
        )
        batch_op.alter_column(
            "created_at",
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=True,
            nullable=False,
        )
        batch_op.alter_column(
            "updated_at",
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=True,
            nullable=False,
        )
        batch_op.alter_column(
            "published_at",
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=True,
            server_default=sa.func.now(),
        )

    op.execute(
        sa.text("UPDATE mushroom_risks SET level = '未知' WHERE level IS NULL")
    )
    op.execute(
        sa.text(
            "UPDATE mushroom_risks SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL"
        )
    )
    op.execute(
        sa.text(
            "UPDATE mushroom_risks SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL"
        )
    )
    _assert_max_length("mushroom_risks", "name", 128)
    _assert_max_length("mushroom_risks", "species", 128)
    with op.batch_alter_table("mushroom_risks") as batch_op:
        batch_op.alter_column(
            "name", existing_type=sa.String(200), type_=sa.String(128), nullable=False
        )
        batch_op.alter_column(
            "species", existing_type=sa.String(200), type_=sa.String(128), nullable=True
        )
        batch_op.alter_column(
            "level", existing_type=sa.String(16), existing_nullable=True, nullable=False
        )
        batch_op.alter_column(
            "created_at",
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=True,
            nullable=False,
        )
        batch_op.alter_column(
            "updated_at",
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=True,
            nullable=False,
        )

    op.add_column(
        "meals", sa.Column("total_kcal", sa.Float(), nullable=False, server_default="0")
    )
    op.add_column(
        "meals", sa.Column("protein", sa.Float(), nullable=False, server_default="0")
    )
    op.add_column("meals", sa.Column("fat", sa.Float(), nullable=False, server_default="0"))
    op.add_column(
        "meals", sa.Column("carbs", sa.Float(), nullable=False, server_default="0")
    )
    op.add_column(
        "meals", sa.Column("sodium", sa.Float(), nullable=False, server_default="0")
    )
    op.add_column("meals", sa.Column("advice", sa.Text(), nullable=True))
    op.add_column(
        "meals", sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.execute(sa.text("UPDATE meals SET captured_at = eaten_at WHERE captured_at IS NULL"))
    op.execute(sa.text("UPDATE meals SET advice = note WHERE advice IS NULL AND note IS NOT NULL"))
    op.execute(
        sa.text("UPDATE meals SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")
    )
    op.execute(
        sa.text("UPDATE meals SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL")
    )
    op.drop_index("ix_meals_eaten_at", table_name="meals")
    with op.batch_alter_table("meals") as batch_op:
        batch_op.alter_column(
            "captured_at",
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=True,
            nullable=False,
            server_default=sa.func.now(),
        )
        batch_op.alter_column(
            "created_at",
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=True,
            nullable=False,
        )
        batch_op.alter_column(
            "updated_at",
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=True,
            nullable=False,
        )
        batch_op.create_foreign_key(
            "fk_meals_user_id_users", "users", ["user_id"], ["id"]
        )
        batch_op.drop_column("eaten_at")
        batch_op.drop_column("note")

    for column in ("grams", "kcal", "protein", "fat", "carbs", "sodium", "confidence"):
        op.execute(sa.text(f"UPDATE meal_items SET {column} = 0 WHERE {column} IS NULL"))
    _assert_max_length("meal_items", "name", 128)
    with op.batch_alter_table("meal_items") as batch_op:
        batch_op.alter_column(
            "name", existing_type=sa.String(200), type_=sa.String(128), nullable=False
        )
        for column in ("grams", "kcal", "protein", "fat", "carbs", "sodium", "confidence"):
            batch_op.alter_column(
                column, existing_type=sa.Float(), existing_nullable=True, nullable=False
            )
        batch_op.create_foreign_key(
            "fk_meal_items_meal_id_meals", "meals", ["meal_id"], ["id"]
        )
        batch_op.drop_column("created_at")
        batch_op.drop_column("updated_at")

    op.create_table(
        "survey_templates",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("type", sa.String(64), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.String(256), nullable=False),
        sa.Column("questions", sa.Text(), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_survey_templates_type", "survey_templates", ["type"], unique=True)

    op.create_table(
        "consult_assignments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("doctor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("first_chat_at", sa.DateTime(), nullable=True),
        sa.Column("last_message_at", sa.DateTime(), nullable=True),
        sa.Column("last_message_preview", sa.String(200), nullable=True),
        *_timestamps(),
    )
    op.create_index(
        "ix_assignment_patient_doctor",
        "consult_assignments",
        ["patient_id", "doctor_id"],
        unique=False,
    )
    op.create_index(
        "ix_consult_assignments_doctor_id", "consult_assignments", ["doctor_id"]
    )
    op.create_index(
        "ix_consult_assignments_patient_id", "consult_assignments", ["patient_id"]
    )

    op.create_table(
        "doctor_presence",
        sa.Column("doctor_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("last_seen", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "survey_responses",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "template_id", sa.Integer(), sa.ForeignKey("survey_templates.id"), nullable=False
        ),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("template_type", sa.String(64), nullable=False),
        sa.Column("user_name", sa.String(64), nullable=False),
        sa.Column("user_phone", sa.String(20), nullable=False),
        sa.Column("submitted_at", sa.String(64), nullable=False),
        sa.Column("total_score", sa.Float(), nullable=False),
        sa.Column("analysis", sa.Text(), nullable=False),
        sa.Column("answers", sa.Text(), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_survey_responses_template_id", "survey_responses", ["template_id"])
    op.create_index(
        "ix_survey_responses_template_type", "survey_responses", ["template_type"]
    )
    op.create_index("ix_survey_responses_user_id", "survey_responses", ["user_id"])

    op.create_table(
        "appointments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column(
            "assignment_id",
            sa.Integer(),
            sa.ForeignKey("consult_assignments.id"),
            nullable=True,
        ),
        sa.UniqueConstraint("patient_id"),
        *_timestamps(),
    )

    op.create_table(
        "consultations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "assignment_id",
            sa.Integer(),
            sa.ForeignKey("consult_assignments.id"),
            nullable=False,
        ),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("doctor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("sender_role", sa.String(16), nullable=False),
        sa.Column("sender_id", sa.Integer(), nullable=False),
        sa.Column("msg_type", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("image_url", sa.String(512), nullable=True),
        sa.Column("consult_target_doctor_id", sa.Integer(), nullable=True),
        sa.Column("consult_target_doctor_name", sa.String(64), nullable=True),
        sa.Column("consult_status", sa.String(16), nullable=True),
        sa.Column("consult_note", sa.String(255), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_consultations_assignment_id", "consultations", ["assignment_id"])
    op.create_index("ix_consultations_doctor_id", "consultations", ["doctor_id"])
    op.create_index("ix_consultations_patient_id", "consultations", ["patient_id"])
    op.create_index("ix_consultations_sender_role", "consultations", ["sender_role"])


def downgrade() -> None:
    op.drop_table("consultations")
    op.drop_table("appointments")
    op.drop_table("survey_responses")
    op.drop_table("doctor_presence")
    op.drop_table("consult_assignments")
    op.drop_table("survey_templates")

    with op.batch_alter_table("meal_items") as batch_op:
        batch_op.drop_constraint("fk_meal_items_meal_id_meals", type_="foreignkey")
        batch_op.alter_column(
            "name", existing_type=sa.String(128), type_=sa.String(200), nullable=False
        )
        for column in ("grams", "kcal", "protein", "fat", "carbs", "sodium", "confidence"):
            batch_op.alter_column(
                column, existing_type=sa.Float(), existing_nullable=False, nullable=True
            )
        batch_op.add_column(
            sa.Column(
                "created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.func.now()
            )
        )
        batch_op.add_column(
            sa.Column(
                "updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.func.now()
            )
        )

    op.add_column("meals", sa.Column("eaten_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("meals", sa.Column("note", sa.String(500), nullable=True))
    op.execute(sa.text("UPDATE meals SET eaten_at = captured_at, note = advice"))
    with op.batch_alter_table("meals") as batch_op:
        batch_op.drop_constraint("fk_meals_user_id_users", type_="foreignkey")
        batch_op.alter_column(
            "eaten_at",
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=True,
            nullable=False,
        )
        batch_op.alter_column(
            "created_at",
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=False,
            nullable=True,
        )
        batch_op.alter_column(
            "updated_at",
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=False,
            nullable=True,
        )
        for column in (
            "total_kcal",
            "protein",
            "fat",
            "carbs",
            "sodium",
            "advice",
            "captured_at",
        ):
            batch_op.drop_column(column)
    op.create_index("ix_meals_eaten_at", "meals", ["eaten_at"])

    with op.batch_alter_table("mushroom_risks") as batch_op:
        batch_op.alter_column(
            "name", existing_type=sa.String(128), type_=sa.String(200), nullable=False
        )
        batch_op.alter_column(
            "species", existing_type=sa.String(128), type_=sa.String(200), nullable=True
        )
        batch_op.alter_column(
            "level", existing_type=sa.String(16), existing_nullable=False, nullable=True
        )
        batch_op.alter_column(
            "created_at",
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=False,
            nullable=True,
        )
        batch_op.alter_column(
            "updated_at",
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=False,
            nullable=True,
        )

    with op.batch_alter_table("knowledge_articles") as batch_op:
        batch_op.alter_column(
            "title", existing_type=sa.String(256), type_=sa.String(200), nullable=False
        )
        batch_op.alter_column(
            "summary", existing_type=sa.String(512), type_=sa.String(500), nullable=True
        )
        batch_op.alter_column(
            "content_html", existing_type=sa.Text(), existing_nullable=False, nullable=True
        )
        batch_op.alter_column(
            "source", existing_type=sa.String(128), type_=sa.String(200), nullable=True
        )
        batch_op.alter_column(
            "version", existing_type=sa.Integer(), existing_nullable=False, nullable=True
        )
        batch_op.alter_column(
            "created_at",
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=False,
            nullable=True,
        )
        batch_op.alter_column(
            "updated_at",
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=False,
            nullable=True,
        )
        batch_op.drop_column("published_at")

    users = sa.table(
        "users", sa.column("id", sa.Integer()), sa.column("openid", sa.String(64))
    )
    op.execute(
        users.update()
        .where(users.c.openid.is_(None))
        .values(openid=sa.literal("legacy-account-") + sa.cast(users.c.id, sa.String()))
    )
    op.drop_index("ix_users_username", table_name="users")
    op.drop_index("ix_users_role", table_name="users")
    op.drop_index("ix_users_phone", table_name="users")
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "openid", existing_type=sa.String(64), existing_nullable=True, nullable=False
        )
        batch_op.alter_column(
            "created_at",
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=False,
            nullable=True,
        )
        batch_op.alter_column(
            "updated_at",
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=False,
            nullable=True,
        )
        for column in (
            "role",
            "username",
            "password_hash",
            "real_name",
            "department",
            "title",
            "intro",
            "is_available",
            "is_vip",
            "vip_expire_at",
            "total_analysis_count",
            "purchased_analysis_count",
            "is_active",
        ):
            batch_op.drop_column(column)
