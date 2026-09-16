"""持久化科普互动：幂等操作、个人收藏、回复和站内消息。"""
from typing import Literal, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, func, delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db
from app.core.security import oauth2_scheme, decode_token, verify_admin_session
from app.models.user import User
from app.models.knowledge import KnowledgeArticle
from app.models.community import ArticleReaction, ArticleComment, CommentLike, CommentReport, CommunityNotification as Notice
from app.services.knowledge_service import _article_to_item
from app.services.wechat_content_security import (
    ContentSecurityRejected,
    ContentSecurityUnavailable,
    check_public_text,
)

router = APIRouter()


async def optional_user(token: Optional[str] = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    if not token:
        return None
    try:
        payload = decode_token(token)
        uid = int(payload.get('sub', ''))
    except (ValueError, TypeError):
        raise HTTPException(401, '请重新登录')
    user = await db.get(User, uid)
    if not user or not user.is_active:
        raise HTTPException(401, '账号不可用，请重新登录')
    if user.role == 'admin':
        verify_admin_session(payload, user)
    return user


async def member(user=Depends(optional_user)):
    if not user:
        raise HTTPException(401, '请先登录')
    return user


async def article_or_404(db, aid, lock=False):
    if lock:
        # 所有文章互动在同一行串行化，避免并发重复记录和计数偏差。
        await db.execute(update(KnowledgeArticle).where(KnowledgeArticle.id == aid).values(
            id=KnowledgeArticle.id, updated_at=KnowledgeArticle.updated_at))
    article = await db.get(KnowledgeArticle, aid)
    if not article:
        raise HTTPException(404, '文章不存在或已下架')
    return article


async def decorate(db, articles, user):
    ids = [a.id for a in articles]
    if not ids:
        return []
    likes = dict((await db.execute(select(ArticleReaction.article_id, func.count()).where(
        ArticleReaction.article_id.in_(ids), ArticleReaction.kind == 'like'
    ).group_by(ArticleReaction.article_id))).all())
    comments = dict((await db.execute(select(ArticleComment.article_id, func.count()).where(
        ArticleComment.article_id.in_(ids), ArticleComment.deleted.is_(False)
    ).group_by(ArticleComment.article_id))).all())
    mine = set()
    if user:
        mine = set((await db.execute(select(ArticleReaction.article_id, ArticleReaction.kind).where(
            ArticleReaction.article_id.in_(ids), ArticleReaction.user_id == user.id))).all())
    return [{**_article_to_item(a), 'likeCount': likes.get(a.id, 0), 'commentCount': comments.get(a.id, 0),
             'liked': (a.id, 'like') in mine, 'favorited': (a.id, 'favorite') in mine} for a in articles]


@router.get('/articles')
async def articles(category: Optional[str] = None, q: str = '', before: int = 0,
                   limit: int = Query(20, ge=1, le=50), user=Depends(optional_user), db: AsyncSession = Depends(get_db)):
    stmt = select(KnowledgeArticle)
    if category:
        stmt = stmt.where(KnowledgeArticle.category == category)
    if q.strip():
        stmt = stmt.where(KnowledgeArticle.title.contains(q.strip()) | KnowledgeArticle.summary.contains(q.strip()))
    if before:
        stmt = stmt.where(KnowledgeArticle.id < before)
    rows = (await db.execute(stmt.order_by(KnowledgeArticle.id.desc()).limit(limit + 1))).scalars().all()
    return {'items': await decorate(db, rows[:limit], user), 'hasMore': len(rows) > limit,
            'nextCursor': rows[limit - 1].id if len(rows) > limit else 0}


@router.get('/articles/{aid}')
async def detail(aid: int, user=Depends(optional_user), db: AsyncSession = Depends(get_db)):
    article = await article_or_404(db, aid)
    result = (await decorate(db, [article], user))[0]
    return {**result, 'contentHtml': article.content_html}


class ReactionBody(BaseModel):
    active: bool


@router.put('/articles/{aid}/reactions/{kind}')
async def react(aid: int, kind: Literal['like', 'favorite'], body: ReactionBody,
                user=Depends(member), db: AsyncSession = Depends(get_db)):
    article = await article_or_404(db, aid, lock=True)
    stmt = select(ArticleReaction).where(ArticleReaction.article_id == aid, ArticleReaction.user_id == user.id, ArticleReaction.kind == kind)
    existing = (await db.execute(stmt)).scalar_one_or_none()
    event = f'{kind}:{aid}:{user.id}'
    if body.active and not existing:
        db.add(ArticleReaction(article_id=aid, user_id=user.id, kind=kind))
        db.add(Notice(recipient_id=user.id, actor_id=user.id, article_id=aid, kind=kind, event_key=event))
    elif not body.active and existing:
        await db.delete(existing)
        await db.execute(delete(Notice).where(Notice.event_key == event))
    await db.commit()
    return (await decorate(db, [article], user))[0]


@router.get('/favorites')
async def favorites(before: int = 0, limit: int = Query(20, ge=1, le=50), user=Depends(member), db: AsyncSession = Depends(get_db)):
    stmt = select(ArticleReaction.id, KnowledgeArticle).join(KnowledgeArticle, KnowledgeArticle.id == ArticleReaction.article_id).where(
        ArticleReaction.user_id == user.id, ArticleReaction.kind == 'favorite')
    if before:
        stmt = stmt.where(ArticleReaction.id < before)
    rows = (await db.execute(stmt.order_by(ArticleReaction.id.desc()).limit(limit + 1))).all()
    return {'items': await decorate(db, [r[1] for r in rows[:limit]], user), 'hasMore': len(rows) > limit,
            'nextCursor': rows[limit - 1][0] if len(rows) > limit else 0}


class CommentBody(BaseModel):
    content: str = Field(min_length=1, max_length=500)
    parent_id: Optional[int] = None
    request_id: str = Field(min_length=8, max_length=80, pattern=r'^[A-Za-z0-9_-]+$')

    @field_validator('content')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('评论不能为空')
        return value.strip()


@router.get('/articles/{aid}/comments')
async def comments(aid: int, before: int = 0, limit: int = Query(20, ge=1, le=50),
                   user=Depends(optional_user), db: AsyncSession = Depends(get_db)):
    await article_or_404(db, aid)
    stmt = select(ArticleComment, User.nickname).join(User, User.id == ArticleComment.user_id).where(
        ArticleComment.article_id == aid, ArticleComment.deleted.is_(False))
    if before:
        stmt = stmt.where(ArticleComment.id < before)
    rows = (await db.execute(stmt.order_by(ArticleComment.id.desc()).limit(limit + 1))).all()
    shown = rows[:limit]
    ids = [c.id for c, _ in shown]
    counts = dict((await db.execute(select(CommentLike.comment_id, func.count()).where(CommentLike.comment_id.in_(ids)).group_by(CommentLike.comment_id))).all()) if ids else {}
    liked = set((await db.execute(select(CommentLike.comment_id).where(CommentLike.comment_id.in_(ids), CommentLike.user_id == user.id))).scalars()) if ids and user else set()
    parent_ids = [c.parent_id for c, _ in shown if c.parent_id]
    parents = {c.id: (c, name) for c, name in (await db.execute(select(ArticleComment, User.nickname).join(User, User.id == ArticleComment.user_id).where(ArticleComment.id.in_(parent_ids)))).all()} if parent_ids else {}
    items = []
    for c, name in shown:
        parent = parents.get(c.parent_id)
        items.append({'id': c.id, 'content': c.content, 'author': name or '健康伙伴',
                      'mine': bool(user and c.user_id == user.id), 'createdAt': c.created_at.isoformat(),
                      'likeCount': counts.get(c.id, 0), 'liked': c.id in liked,
                      'replyTo': (parent[1] or '健康伙伴') if parent else '',
                      'parentContent': ('原评论已删除' if parent[0].deleted else parent[0].content) if parent else ''})
    return {'items': items, 'hasMore': len(rows) > limit, 'nextCursor': shown[-1][0].id if len(rows) > limit else 0}


@router.post('/articles/{aid}/comments')
async def post_comment(aid: int, body: CommentBody, user=Depends(member), db: AsyncSession = Depends(get_db)):
    await article_or_404(db, aid, lock=True)
    existing = (await db.execute(select(ArticleComment).where(ArticleComment.user_id == user.id, ArticleComment.request_id == body.request_id))).scalar_one_or_none()
    if existing:
        if existing.article_id != aid or existing.content != body.content or existing.parent_id != body.parent_id or existing.deleted:
            raise HTTPException(409, '这次提交已处理，请刷新后重试')
        return {'id': existing.id}
    parent = await db.get(ArticleComment, body.parent_id) if body.parent_id else None
    if body.parent_id and (not parent or parent.article_id != aid or parent.deleted):
        raise HTTPException(400, '回复的评论不存在或已删除')
    try:
        await check_public_text(body.content, user.openid)
    except ContentSecurityRejected as exc:
        raise HTTPException(400, str(exc)) from exc
    except ContentSecurityUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    comment = ArticleComment(article_id=aid, user_id=user.id, content=body.content, parent_id=body.parent_id, request_id=body.request_id)
    db.add(comment)
    await db.flush()
    db.add(Notice(recipient_id=user.id, actor_id=user.id, article_id=aid, comment_id=comment.id, kind='comment', event_key=f'comment:{comment.id}'))
    if parent and parent.user_id != user.id:
        db.add(Notice(recipient_id=parent.user_id, actor_id=user.id, article_id=aid, comment_id=comment.id, kind='reply', event_key=f'reply:{comment.id}'))
    await db.commit()
    return {'id': comment.id}


@router.delete('/comments/{cid}')
async def remove_comment(cid: int, user=Depends(member), db: AsyncSession = Depends(get_db)):
    c = await db.get(ArticleComment, cid)
    if not c:
        raise HTTPException(404, '评论不存在')
    if c.user_id != user.id and user.role != 'admin':
        raise HTTPException(403, '只能删除自己的评论')
    await article_or_404(db, c.article_id, lock=True)
    c.deleted = True
    c.content = ''
    await db.execute(delete(CommentLike).where(CommentLike.comment_id == cid))
    await db.execute(delete(CommentReport).where(CommentReport.comment_id == cid))
    await db.execute(delete(Notice).where(Notice.comment_id == cid))
    await db.commit()
    return {'ok': True}


@router.put('/comments/{cid}/like')
async def like_comment(cid: int, body: ReactionBody, user=Depends(member), db: AsyncSession = Depends(get_db)):
    c = await db.get(ArticleComment, cid)
    if not c:
        raise HTTPException(404, '评论不存在')
    await article_or_404(db, c.article_id, lock=True)
    await db.refresh(c)
    if c.deleted:
        raise HTTPException(404, '评论已删除')
    existing = (await db.execute(select(CommentLike).where(CommentLike.comment_id == cid, CommentLike.user_id == user.id))).scalar_one_or_none()
    event = f'comment_like:{cid}:{user.id}'
    if body.active and not existing:
        db.add(CommentLike(comment_id=cid, user_id=user.id))
        if c.user_id != user.id:
            db.add(Notice(recipient_id=c.user_id, actor_id=user.id, article_id=c.article_id, comment_id=cid, kind='comment_like', event_key=event))
    elif not body.active and existing:
        await db.delete(existing)
        await db.execute(delete(Notice).where(Notice.event_key == event))
    await db.commit()
    count = (await db.execute(select(func.count()).select_from(CommentLike).where(CommentLike.comment_id == cid))).scalar_one()
    return {'liked': body.active, 'likeCount': count}


class ReportBody(BaseModel):
    reason: Literal['垃圾广告', '不实信息', '不友善评论']


@router.post('/comments/{cid}/report')
async def report_comment(cid: int, body: ReportBody, user=Depends(member), db: AsyncSession = Depends(get_db)):
    comment = await db.get(ArticleComment, cid)
    if not comment or comment.deleted:
        raise HTTPException(404, '评论不存在')
    if comment.user_id == user.id:
        raise HTTPException(400, '不能举报自己的评论')
    await article_or_404(db, comment.article_id, lock=True)
    existing = (await db.execute(select(CommentReport).where(CommentReport.comment_id == cid, CommentReport.reporter_id == user.id))).scalar_one_or_none()
    if not existing:
        db.add(CommentReport(comment_id=cid, reporter_id=user.id, reason=body.reason))
        await db.commit()
    return {'ok': True}


@router.get('/moderation/reports')
async def moderation_reports(limit: int = Query(50, ge=1, le=100), user=Depends(member), db: AsyncSession = Depends(get_db)):
    if user.role != 'admin':
        raise HTTPException(403, '仅管理员可查看')
    rows = (await db.execute(select(CommentReport, ArticleComment.content).join(
        ArticleComment, ArticleComment.id == CommentReport.comment_id).where(
        CommentReport.status == 'pending').order_by(CommentReport.id.desc()).limit(limit))).all()
    return [{'id': r.id, 'commentId': r.comment_id, 'reason': r.reason, 'content': content,
             'createdAt': r.created_at.isoformat()} for r, content in rows]


class ModerateBody(BaseModel):
    action: Literal['hide', 'dismiss']


@router.post('/moderation/reports/{report_id}')
async def moderate(report_id: int, body: ModerateBody, user=Depends(member), db: AsyncSession = Depends(get_db)):
    if user.role != 'admin':
        raise HTTPException(403, '仅管理员可处理')
    report = await db.get(CommentReport, report_id)
    if not report:
        raise HTTPException(404, '举报记录不存在')
    comment = await db.get(ArticleComment, report.comment_id)
    if not comment:
        raise HTTPException(404, '评论不存在')
    await article_or_404(db, comment.article_id, lock=True)
    if body.action == 'hide' and not comment.deleted:
        comment.deleted = True
        comment.content = ''
        await db.execute(delete(CommentLike).where(CommentLike.comment_id == comment.id))
        await db.execute(delete(Notice).where(Notice.comment_id == comment.id))
    await db.execute(update(CommentReport).where(CommentReport.comment_id == comment.id).values(status='resolved'))
    await db.commit()
    return {'ok': True}


@router.get('/notifications/unread')
async def unread(user=Depends(member), db: AsyncSession = Depends(get_db)):
    count = (await db.execute(select(func.count()).select_from(Notice).where(Notice.recipient_id == user.id, Notice.is_read.is_(False)))).scalar_one()
    return {'count': count}


@router.get('/notifications')
async def notifications(kind: Literal['all', 'received', 'like', 'comment', 'favorite'] = 'all', before: int = 0,
                        limit: int = Query(20, ge=1, le=50), user=Depends(member), db: AsyncSession = Depends(get_db)):
    stmt = select(Notice, User.nickname, KnowledgeArticle.title, ArticleComment.content).join(User, User.id == Notice.actor_id).join(
        KnowledgeArticle, KnowledgeArticle.id == Notice.article_id).outerjoin(ArticleComment, ArticleComment.id == Notice.comment_id).where(Notice.recipient_id == user.id)
    if kind == 'received':
        stmt = stmt.where(Notice.actor_id != user.id)
    elif kind != 'all':
        stmt = stmt.where(Notice.kind.in_({'like': ['like', 'comment_like'], 'comment': ['comment', 'reply'], 'favorite': ['favorite']}[kind]))
    if before:
        stmt = stmt.where(Notice.id < before)
    rows = (await db.execute(stmt.order_by(Notice.id.desc()).limit(limit + 1))).all()
    return {'items': [{'id': n.id, 'kind': n.kind, 'actor': name or '健康伙伴', 'self': n.actor_id == user.id,
                       'articleId': n.article_id, 'articleTitle': title, 'commentId': n.comment_id,
                       'content': content or '', 'read': n.is_read, 'createdAt': n.created_at.isoformat()}
                      for n, name, title, content in rows[:limit]], 'hasMore': len(rows) > limit,
            'nextCursor': rows[limit - 1][0].id if len(rows) > limit else 0}


@router.post('/notifications/read-all')
async def read_all(user=Depends(member), db: AsyncSession = Depends(get_db)):
    await db.execute(update(Notice).where(Notice.recipient_id == user.id, Notice.is_read.is_(False)).values(is_read=True))
    await db.commit()
    return {'ok': True}


@router.post('/notifications/{nid}/read')
async def read_one(nid: int, user=Depends(member), db: AsyncSession = Depends(get_db)):
    result = await db.execute(update(Notice).where(Notice.id == nid, Notice.recipient_id == user.id).values(is_read=True))
    if not result.rowcount:
        raise HTTPException(404, '消息不存在')
    await db.commit()
    return {'ok': True}
