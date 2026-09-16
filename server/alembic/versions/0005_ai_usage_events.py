"""Store AI quota reservations in the primary database.

Revision ID: 0005_ai_usage_events
Revises: 0004_current_application_schema
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0005_ai_usage_events"
down_revision: Union[str, None] = "0004_current_application_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_usage_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_ai_usage_events_user_id", "ai_usage_events", ["user_id"], unique=False
    )
    op.create_index(
        "ix_ai_usage_events_created_at", "ai_usage_events", ["created_at"], unique=False
    )
    op.create_index(
        "ix_ai_usage_events_user_created",
        "ai_usage_events",
        ["user_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("ai_usage_events")
