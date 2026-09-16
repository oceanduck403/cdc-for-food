"""Account self-deletion privacy and referential-integrity regression tests."""
from io import BytesIO
from uuid import uuid4

import pytest
from PIL import Image
from sqlalchemy import func, select, text

from app.config import settings
from app.core.security import admin_auth_fingerprint, create_access_token, hash_password
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
from app.models.knowledge import KnowledgeArticle
from app.models.meal import Meal, MealItem
from app.models.survey import SurveyResponse, SurveyTemplate
from app.models.user import User
from app.services.media_service import store_avatar, store_chat_image

pytestmark = pytest.mark.asyncio


def auth_header(user: User) -> dict[str, str]:
    extra = {"role": user.role}
    if user.role == "admin":
        extra["admin_auth"] = admin_auth_fingerprint(user)
    return {"Authorization": f"Bearer {create_access_token(str(user.id), extra=extra)}"}


async def count(db, model, *conditions) -> int:
    statement = select(func.count()).select_from(model)
    if conditions:
        statement = statement.where(*conditions)
    return int((await db.execute(statement)).scalar_one())


async def test_user_foreign_key_inventory_is_accounted_for():
    """New user-owned tables must be considered by the deletion workflow."""
    actual = {
        (table.name, column.name)
        for table in User.metadata.tables.values()
        for column in table.columns
        for foreign_key in column.foreign_keys
        if foreign_key.target_fullname == "users.id"
    }
    assert actual == {
        ("appointments", "patient_id"),
        ("ai_usage_events", "user_id"),
        ("article_comments", "user_id"),
        ("article_reactions", "user_id"),
        ("comment_likes", "user_id"),
        ("comment_reports", "reporter_id"),
        ("community_notifications", "actor_id"),
        ("community_notifications", "recipient_id"),
        ("consult_assignments", "doctor_id"),
        ("consult_assignments", "patient_id"),
        ("consultations", "doctor_id"),
        ("consultations", "patient_id"),
        ("doctor_presence", "doctor_id"),
        ("meals", "user_id"),
        ("survey_responses", "user_id"),
    }


async def test_patient_can_permanently_delete_owned_data_without_public_content(
    client, db, tmp_path, monkeypatch
):
    await db.execute(text("PRAGMA foreign_keys = ON"))
    await db.commit()
    monkeypatch.setattr(settings, "media_storage_dir", str(tmp_path / "private-media"))
    image_buffer = BytesIO()
    Image.new("RGB", (80, 80), "#6aa6be").save(image_buffer, "JPEG")
    image_bytes = image_buffer.getvalue()
    suffix = uuid4().hex
    patient = User(role="patient", openid=f"delete-{suffix}", nickname="待注销用户", phone=f"13{suffix[:9]}")
    other = User(role="patient", openid=f"other-{suffix}", nickname="其他用户")
    doctor = User(role="doctor", username=f"doctor-{suffix}", password_hash=hash_password("Doctor-123"))
    db.add_all([patient, other, doctor])
    await db.flush()

    article = KnowledgeArticle(category="safety", title=f"公共科普-{suffix}", content_html="疾控素材")
    template = SurveyTemplate(type=f"public-{suffix}", name="公共评估模板", questions="[]")
    db.add_all([article, template])
    await db.flush()

    own_comment = ArticleComment(
        article_id=article.id,
        user_id=patient.id,
        content="我的评论",
        request_id=f"own-{suffix}",
    )
    other_comment = ArticleComment(
        article_id=article.id,
        user_id=other.id,
        content="其他人的评论",
        request_id=f"other-{suffix}",
    )
    db.add_all([own_comment, other_comment])
    await db.flush()
    reply = ArticleComment(
        article_id=article.id,
        user_id=other.id,
        parent_id=own_comment.id,
        content="回复待注销用户",
        request_id=f"reply-{suffix}",
    )
    db.add_all([
        reply,
        ArticleReaction(article_id=article.id, user_id=patient.id, kind="favorite"),
        CommentLike(comment_id=own_comment.id, user_id=other.id),
        CommentLike(comment_id=other_comment.id, user_id=patient.id),
        CommentReport(comment_id=own_comment.id, reporter_id=other.id, reason="不实信息"),
        CommentReport(comment_id=other_comment.id, reporter_id=patient.id, reason="垃圾广告"),
        CommunityNotification(
            recipient_id=patient.id,
            actor_id=other.id,
            article_id=article.id,
            comment_id=own_comment.id,
            kind="reply",
            event_key=f"notice-recipient-{suffix}",
        ),
        CommunityNotification(
            recipient_id=other.id,
            actor_id=patient.id,
            article_id=article.id,
            comment_id=other_comment.id,
            kind="comment_like",
            event_key=f"notice-actor-{suffix}",
        ),
    ])

    assignment = ConsultAssignment(patient_id=patient.id, doctor_id=doctor.id, status="active")
    db.add(assignment)
    await db.flush()
    avatar = store_avatar(image_bytes)
    chat_image = store_chat_image(image_bytes, assignment.id)
    patient.avatar = avatar.reference
    db.add_all([
        Appointment(patient_id=patient.id, status="assigned", assignment_id=assignment.id),
        Consultation(
            assignment_id=assignment.id,
            patient_id=patient.id,
            doctor_id=doctor.id,
            sender_role="patient",
            sender_id=patient.id,
            msg_type="image",
            content="[图片]",
            image_url=chat_image.reference,
        ),
    ])

    meal = Meal(user_id=patient.id, total_kcal=100, image_url="private-meal.jpg")
    db.add(meal)
    await db.flush()
    db.add(MealItem(meal_id=meal.id, name="测试餐食", grams=100, kcal=100))
    db.add(
        SurveyResponse(
            template_id=template.id,
            user_id=patient.id,
            template_type=template.type,
            user_name="待注销用户",
            user_phone=patient.phone or "",
            answers='{"health":"private"}',
        )
    )
    db.add(AiUsageEvent(user_id=patient.id))
    await db.commit()

    patient_id = patient.id
    other_id = other.id
    doctor_id = doctor.id
    reply_id = reply.id
    article_id = article.id
    template_id = template.id
    headers = auth_header(patient)
    response = await client.request(
        "DELETE",
        "/api/v1/users/me",
        json={"confirmation": "注销账号"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"deleted": True}
    assert not avatar.path.exists()
    assert not chat_image.path.exists()

    db.expire_all()
    assert await db.get(User, patient_id) is None
    assert await count(db, SurveyResponse, SurveyResponse.user_id == patient_id) == 0
    assert await count(db, AiUsageEvent, AiUsageEvent.user_id == patient_id) == 0
    assert await count(db, Meal, Meal.user_id == patient_id) == 0
    assert await count(db, Consultation, Consultation.patient_id == patient_id) == 0
    assert await count(db, ConsultAssignment, ConsultAssignment.patient_id == patient_id) == 0
    assert await count(db, Appointment, Appointment.patient_id == patient_id) == 0
    assert await count(db, ArticleComment, ArticleComment.user_id == patient_id) == 0
    assert await count(db, ArticleReaction, ArticleReaction.user_id == patient_id) == 0
    assert await count(db, CommentLike, CommentLike.user_id == patient_id) == 0
    assert await count(db, CommentReport, CommentReport.reporter_id == patient_id) == 0
    assert await count(
        db,
        CommunityNotification,
        (CommunityNotification.recipient_id == patient_id) | (CommunityNotification.actor_id == patient_id),
    ) == 0

    # Disease-control content and content created by somebody else are retained.
    assert await db.get(KnowledgeArticle, article_id) is not None
    assert await db.get(SurveyTemplate, template_id) is not None
    retained_reply = await db.get(ArticleComment, reply_id)
    assert retained_reply is not None
    assert retained_reply.parent_id is None
    assert await db.get(User, other_id) is not None
    assert await db.get(User, doctor_id) is not None

    # A previously issued JWT can no longer access any authenticated endpoint.
    stale = await client.get("/api/v1/users/me", headers=headers)
    assert stale.status_code == 401


async def test_deletion_requires_exact_confirmation_and_patient_role(client, db):
    suffix = uuid4().hex
    patient = User(role="patient", openid=f"confirm-{suffix}", nickname="保留用户")
    admin = User(
        role="admin",
        username=f"admin-{suffix}",
        password_hash=hash_password("Admin-password-123"),
    )
    doctor = User(
        role="doctor",
        username=f"managed-doctor-{suffix}",
        password_hash=hash_password("Doctor-password-123"),
    )
    db.add_all([patient, admin, doctor])
    await db.commit()

    assert (await client.delete("/api/v1/users/me")).status_code == 401
    invalid = await client.request(
        "DELETE",
        "/api/v1/users/me",
        json={"confirmation": "确认"},
        headers=auth_header(patient),
    )
    assert invalid.status_code == 422
    assert await db.get(User, patient.id) is not None

    for managed in (admin, doctor):
        forbidden = await client.request(
            "DELETE",
            "/api/v1/users/me",
            json={"confirmation": "注销账号"},
            headers=auth_header(managed),
        )
        assert forbidden.status_code == 403
        assert await db.get(User, managed.id) is not None
