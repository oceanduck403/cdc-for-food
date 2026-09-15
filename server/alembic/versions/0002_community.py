"""Article interactions and in-app notifications.

Revision ID: 0002_community
Revises: 0001_init
"""
from alembic import op
import sqlalchemy as sa

revision = '0002_community'
down_revision = '0001_init'
branch_labels = None
depends_on = None


def timestamps():
    return [sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)]


def upgrade():
    op.create_table('article_reactions', sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('article_id', sa.Integer(), sa.ForeignKey('knowledge_articles.id'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('kind', sa.String(16), nullable=False), *timestamps(),
        sa.UniqueConstraint('article_id', 'user_id', 'kind', name='uq_article_reaction'))
    op.create_index('ix_article_reactions_article_id', 'article_reactions', ['article_id'])
    op.create_index('ix_article_reactions_user_id', 'article_reactions', ['user_id'])

    op.create_table('article_comments', sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('article_id', sa.Integer(), sa.ForeignKey('knowledge_articles.id'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('parent_id', sa.Integer(), sa.ForeignKey('article_comments.id'), nullable=True),
        sa.Column('content', sa.Text(), nullable=False), sa.Column('deleted', sa.Boolean(), nullable=False),
        sa.Column('request_id', sa.String(80), nullable=False), *timestamps(),
        sa.UniqueConstraint('user_id', 'request_id', name='uq_article_comment_request'))
    op.create_index('ix_article_comments_article_id', 'article_comments', ['article_id'])
    op.create_index('ix_article_comments_user_id', 'article_comments', ['user_id'])

    op.create_table('comment_likes', sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('comment_id', sa.Integer(), sa.ForeignKey('article_comments.id'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False), *timestamps(),
        sa.UniqueConstraint('comment_id', 'user_id', name='uq_comment_like'))
    op.create_index('ix_comment_likes_comment_id', 'comment_likes', ['comment_id'])
    op.create_index('ix_comment_likes_user_id', 'comment_likes', ['user_id'])

    op.create_table('comment_reports', sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('comment_id', sa.Integer(), sa.ForeignKey('article_comments.id'), nullable=False),
        sa.Column('reporter_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('reason', sa.String(32), nullable=False), sa.Column('status', sa.String(16), nullable=False),
        *timestamps(), sa.UniqueConstraint('comment_id', 'reporter_id', name='uq_comment_report'))
    op.create_index('ix_comment_reports_comment_id', 'comment_reports', ['comment_id'])
    op.create_index('ix_comment_reports_reporter_id', 'comment_reports', ['reporter_id'])
    op.create_index('ix_comment_reports_status', 'comment_reports', ['status'])

    op.create_table('community_notifications', sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('recipient_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('actor_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('article_id', sa.Integer(), sa.ForeignKey('knowledge_articles.id'), nullable=False),
        sa.Column('comment_id', sa.Integer(), sa.ForeignKey('article_comments.id'), nullable=True),
        sa.Column('kind', sa.String(20), nullable=False), sa.Column('event_key', sa.String(120), nullable=False, unique=True),
        sa.Column('is_read', sa.Boolean(), nullable=False), *timestamps())
    op.create_index('ix_community_notifications_recipient_id', 'community_notifications', ['recipient_id'])
    op.create_index('ix_community_notifications_is_read', 'community_notifications', ['is_read'])


def downgrade():
    for name in ('community_notifications', 'comment_reports', 'comment_likes', 'article_comments', 'article_reactions'):
        op.drop_table(name)
