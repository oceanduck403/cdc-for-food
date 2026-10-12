"""Keep source form revisions and historical question snapshots.

Revision ID: 0006_original_survey_catalog
Revises: 0005_ai_usage_events
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0006_original_survey_catalog"
down_revision: Union[str, None] = "0005_ai_usage_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "survey_templates",
        sa.Column("catalog_revision", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "survey_responses", sa.Column("questions_snapshot", sa.Text(), nullable=True)
    )
    # Snapshot before the application restores original Word forms. Existing
    # answer ids may refer to an older, incomplete digital questionnaire.
    op.execute(
        sa.text(
            "UPDATE survey_responses SET questions_snapshot = "
            "(SELECT survey_templates.questions FROM survey_templates "
            "WHERE survey_templates.id = survey_responses.template_id) "
            "WHERE questions_snapshot IS NULL"
        )
    )
    with op.batch_alter_table("survey_responses") as batch_op:
        batch_op.alter_column("total_score", existing_type=sa.Float(), nullable=True)


def downgrade() -> None:
    # Downgrading to the old non-null score schema must never silently turn an
    # unscored source form into a numeric result.
    unscored = op.get_bind().execute(
        sa.text("SELECT 1 FROM survey_responses WHERE total_score IS NULL LIMIT 1")
    ).first()
    if unscored:
        raise RuntimeError("cannot downgrade while unscored survey responses exist")
    with op.batch_alter_table("survey_responses") as batch_op:
        batch_op.alter_column("total_score", existing_type=sa.Float(), nullable=False)
    op.drop_column("survey_responses", "questions_snapshot")
    op.drop_column("survey_templates", "catalog_revision")
