"""Patient account deletion with explicit, ordered personal-data cleanup."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Iterator, TypeVar

from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BusinessError
from app.models.appointment import Appointment
from app.models.ai_usage import AiUsageEvent
from app.models.chat import ConsultAssignment, Consultation
from app.models.community import (
    ArticleComment,
    ArticleReaction,
    CommentLike,
    CommentReport,
    CommunityNotification,
)
from app.models.meal import Meal, MealItem
from app.models.survey import SurveyResponse
from app.models.user import User


T = TypeVar("T")


@dataclass(frozen=True)
class DeletedAccount:
    """Non-identifying cleanup metadata needed after the database commit."""

    user_id: int
    avatar: str | None
    chat_assignment_ids: tuple[int, ...]


def _chunks(values: Iterable[T], size: int = 500) -> Iterator[list[T]]:
    chunk: list[T] = []
    for value in values:
        chunk.append(value)
        if len(chunk) == size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


async def delete_patient_account(db: AsyncSession, user_id: str) -> DeletedAccount:
    """Permanently delete one patient's account and all user-owned records.

    Shared disease-control content (knowledge articles, risk points and survey
    templates) is intentionally retained.  Statements are ordered explicitly so
    the operation also works on databases that enforce foreign keys and do not
    define ``ON DELETE CASCADE``.
    """
    try:
        uid = int(user_id)
    except (TypeError, ValueError) as exc:
        raise BusinessError("INVALID_SESSION", "登录状态无效，请重新登录", status_code=401) from exc

    user = await db.get(User, uid)
    if not user:
        raise BusinessError("USER_NOT_FOUND", "用户不存在或已注销", status_code=404)
    if user.role == "admin":
        raise BusinessError("ACCOUNT_DELETE_FORBIDDEN", "管理员账号不能在小程序内注销", status_code=403)
    if user.role != "patient":
        raise BusinessError("ACCOUNT_DELETE_FORBIDDEN", "该账号由管理员统一管理，不能自行注销", status_code=403)

    avatar = user.avatar
    comment_ids = list(
        (await db.execute(select(ArticleComment.id).where(ArticleComment.user_id == uid))).scalars()
    )
    meal_ids = list((await db.execute(select(Meal.id).where(Meal.user_id == uid))).scalars())
    assignment_ids = tuple(
        (await db.execute(
            select(ConsultAssignment.id).where(ConsultAssignment.patient_id == uid)
        )).scalars()
    )

    try:
        # Remove every notification that identifies the user as sender or recipient.
        # Notifications referring to one of their comments must be removed before
        # the comment rows themselves.
        await db.execute(
            delete(CommunityNotification).where(
                or_(
                    CommunityNotification.recipient_id == uid,
                    CommunityNotification.actor_id == uid,
                )
            )
        )
        await db.execute(delete(CommentLike).where(CommentLike.user_id == uid))
        await db.execute(delete(CommentReport).where(CommentReport.reporter_id == uid))

        for ids in _chunks(comment_ids):
            await db.execute(
                delete(CommunityNotification).where(CommunityNotification.comment_id.in_(ids))
            )
            await db.execute(delete(CommentLike).where(CommentLike.comment_id.in_(ids)))
            await db.execute(delete(CommentReport).where(CommentReport.comment_id.in_(ids)))
            # Replies written by other people remain their data.  Detaching their
            # parent avoids deleting or corrupting those replies.
            await db.execute(
                update(ArticleComment)
                .where(ArticleComment.parent_id.in_(ids))
                .values(parent_id=None)
            )

        await db.execute(delete(ArticleComment).where(ArticleComment.user_id == uid))
        await db.execute(delete(ArticleReaction).where(ArticleReaction.user_id == uid))

        # Appointment rows point at assignments, and messages point at both the
        # patient and assignment; delete in dependency order.
        await db.execute(delete(Appointment).where(Appointment.patient_id == uid))
        await db.execute(delete(Consultation).where(Consultation.patient_id == uid))
        await db.execute(delete(ConsultAssignment).where(ConsultAssignment.patient_id == uid))

        await db.execute(delete(SurveyResponse).where(SurveyResponse.user_id == uid))
        await db.execute(delete(AiUsageEvent).where(AiUsageEvent.user_id == uid))
        for ids in _chunks(meal_ids):
            await db.execute(delete(MealItem).where(MealItem.meal_id.in_(ids)))
        await db.execute(delete(Meal).where(Meal.user_id == uid))

        await db.delete(user)
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    return DeletedAccount(
        user_id=uid,
        avatar=avatar,
        chat_assignment_ids=assignment_ids,
    )


__all__ = ["DeletedAccount", "delete_patient_account"]
