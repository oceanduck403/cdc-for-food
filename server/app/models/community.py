"""文章互动与站内通知；收藏和个人动态只向本人提供。"""
from typing import Optional
from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin


class ArticleReaction(Base, TimestampMixin):
    __tablename__ = 'article_reactions'
    __table_args__ = (UniqueConstraint('article_id', 'user_id', 'kind'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    article_id: Mapped[int] = mapped_column(ForeignKey('knowledge_articles.id'), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    kind: Mapped[str] = mapped_column(String(16))


class ArticleComment(Base, TimestampMixin):
    __tablename__ = 'article_comments'
    __table_args__ = (UniqueConstraint('user_id', 'request_id'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    article_id: Mapped[int] = mapped_column(ForeignKey('knowledge_articles.id'), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    parent_id: Mapped[Optional[int]] = mapped_column(ForeignKey('article_comments.id'), nullable=True)
    content: Mapped[str] = mapped_column(Text)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    request_id: Mapped[str] = mapped_column(String(80))


class CommentLike(Base, TimestampMixin):
    __tablename__ = 'comment_likes'
    __table_args__ = (UniqueConstraint('comment_id', 'user_id'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    comment_id: Mapped[int] = mapped_column(ForeignKey('article_comments.id'), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)


class CommentReport(Base, TimestampMixin):
    __tablename__ = 'comment_reports'
    __table_args__ = (UniqueConstraint('comment_id', 'reporter_id'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    comment_id: Mapped[int] = mapped_column(ForeignKey('article_comments.id'), index=True)
    reporter_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    reason: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default='pending', index=True)


class CommunityNotification(Base, TimestampMixin):
    __tablename__ = 'community_notifications'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recipient_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    article_id: Mapped[int] = mapped_column(ForeignKey('knowledge_articles.id'))
    comment_id: Mapped[Optional[int]] = mapped_column(ForeignKey('article_comments.id'), nullable=True)
    kind: Mapped[str] = mapped_column(String(20))
    event_key: Mapped[str] = mapped_column(String(120), unique=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
