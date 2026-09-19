"""问卷管理 API"""
import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_admin, current_user_id, get_db
from app.models.survey import SurveyTemplate, SurveyResponse

router = APIRouter(tags=["问卷管理"])


# ── 患者端 API（公开，不需要登录）─────────────────────────────

@router.get("/templates")
async def list_templates(
    db: AsyncSession = Depends(get_db),
):
    """获取已启用的问卷模板列表（患者可见）"""
    result = await db.execute(
        select(SurveyTemplate)
        .where(SurveyTemplate.is_active.is_(True))
        .order_by(SurveyTemplate.sort_order, SurveyTemplate.id)
    )
    templates = result.scalars().all()
    return [
        {
            "id": t.id,
            "type": t.type,
            "name": t.name,
            "description": t.description,
            "category": t.category,
            "questions": json.loads(t.questions) if t.questions else [],
        }
        for t in templates
    ]


@router.get("/templates/{template_id}")
async def get_template(
    template_id: int,
    db: AsyncSession = Depends(get_db),
):
    """获取单个问卷模板详情"""
    result = await db.execute(
        select(SurveyTemplate).where(
            SurveyTemplate.id == template_id,
            SurveyTemplate.is_active.is_(True),
        )
    )
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="问卷模板不存在或已停用")
    return {
        "id": t.id,
        "type": t.type,
        "name": t.name,
        "description": t.description,
        "category": t.category,
        "questions": json.loads(t.questions) if t.questions else [],
    }


@router.get("/my-responses")
async def list_my_responses(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(current_user_id),
):
    """获取我的问卷填写记录"""
    result = await db.execute(
        select(SurveyResponse, SurveyTemplate.name)
        .outerjoin(SurveyTemplate, SurveyTemplate.id == SurveyResponse.template_id)
        .where(SurveyResponse.user_id == int(user_id))
        .order_by(SurveyResponse.created_at.desc())
    )
    responses = result.all()
    return [
        {
            "id": r.id,
            "template_id": r.template_id,
            "template_type": r.template_type,
            "template_name": template_name or r.template_type,
            "user_name": r.user_name,
            "submitted_at": r.submitted_at,
            "total_score": r.total_score,
            "analysis": r.analysis,
        }
        for r, template_name in responses
    ]


@router.get("/my-responses/{response_id}")
async def get_my_response_detail(
    response_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(current_user_id),
):
    """获取我的单个问卷提交详情"""
    result = await db.execute(
        select(SurveyResponse)
        .where(SurveyResponse.id == response_id)
        .where(SurveyResponse.user_id == int(user_id))
    )
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="记录不存在")

    # 获取关联模板（题目结构）
    t_result = await db.execute(
        select(SurveyTemplate).where(SurveyTemplate.id == r.template_id)
    )
    template = t_result.scalar_one_or_none()

    return {
        "id": r.id,
        "template_id": r.template_id,
        "template_type": r.template_type,
        "template_name": template.name if template else "",
        "user_name": r.user_name,
        "user_phone": r.user_phone,
        "submitted_at": r.submitted_at,
        "total_score": r.total_score,
        "analysis": r.analysis,
        "answers": json.loads(r.answers) if r.answers else {},
        "questions": json.loads(template.questions) if template and template.questions else [],
    }


@router.post("/responses")
async def submit_response(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(current_user_id),
):
    """提交问卷答案"""
    template_id = payload.get("template_id")
    if not template_id:
        raise HTTPException(status_code=400, detail="缺少 template_id")

    # 验证模板存在
    result = await db.execute(
        select(SurveyTemplate).where(
            SurveyTemplate.id == template_id,
            SurveyTemplate.is_active.is_(True),
        )
    )
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="问卷模板不存在或已停用")

    answers = payload.get("answers", {})
    total_score = payload.get("total_score", 0)
    analysis = payload.get("analysis", "")
    user_name = payload.get("user_name", "")
    user_phone = payload.get("user_phone", "")
    submitted_at = payload.get("submitted_at", "")

    resp = SurveyResponse(
        template_id=template_id,
        user_id=int(user_id),
        template_type=template.type,
        user_name=user_name,
        user_phone=user_phone,
        submitted_at=submitted_at,
        total_score=total_score,
        analysis=analysis,
        answers=json.dumps(answers, ensure_ascii=False),
    )
    db.add(resp)
    await db.commit()
    await db.refresh(resp)
    return {"id": resp.id, "message": "提交成功"}


# ── 管理员端 API ───────────────────────────────────────────

@router.get("/admin/templates")
async def admin_list_templates(
    db: AsyncSession = Depends(get_db),
    _=Depends(current_admin),
):
    """管理员：获取所有问卷模板（含未启用的）"""
    result = await db.execute(select(SurveyTemplate).order_by(SurveyTemplate.sort_order))
    templates = result.scalars().all()
    return [
        {
            "id": t.id,
            "type": t.type,
            "name": t.name,
            "description": t.description,
            "category": t.category,
            "is_active": t.is_active,
            "sort_order": t.sort_order,
            "questions": json.loads(t.questions) if t.questions else [],
        }
        for t in templates
    ]


@router.post("/admin/templates")
async def admin_create_template(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _=Depends(current_admin),
):
    """管理员：创建问卷模板"""
    name = payload.get("name", "").strip()
    template_type = payload.get("type", "").strip()
    if not name or not template_type:
        raise HTTPException(status_code=400, detail="名称和类型不能为空")

    # 检查类型唯一
    result = await db.execute(
        select(SurveyTemplate).where(SurveyTemplate.type == template_type)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="该类型已存在，请使用其他类型标识")

    template = SurveyTemplate(
        type=template_type,
        name=name,
        description=payload.get("description", ""),
        category=payload.get("category", "体重管理"),
        questions=json.dumps(payload.get("questions", []), ensure_ascii=False),
        is_active=payload.get("is_active", True),
        sort_order=payload.get("sort_order", 0),
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return {"id": template.id, "message": "创建成功"}


@router.put("/admin/templates/{template_id}")
async def admin_update_template(
    template_id: int,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _=Depends(current_admin),
):
    """管理员：更新问卷模板"""
    result = await db.execute(
        select(SurveyTemplate).where(SurveyTemplate.id == template_id)
    )
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="模板不存在")

    if "name" in payload:
        t.name = payload["name"]
    if "description" in payload:
        t.description = payload["description"]
    if "category" in payload:
        t.category = payload["category"]
    if "questions" in payload:
        t.questions = json.dumps(payload["questions"], ensure_ascii=False)
    if "is_active" in payload:
        t.is_active = payload["is_active"]
    if "sort_order" in payload:
        t.sort_order = payload["sort_order"]

    await db.commit()
    return {"message": "更新成功"}


@router.delete("/admin/templates/{template_id}")
async def admin_delete_template(
    template_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(current_admin),
):
    """管理员：删除问卷模板（软删除：设为未激活）"""
    result = await db.execute(
        select(SurveyTemplate).where(SurveyTemplate.id == template_id)
    )
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="模板不存在")
    t.is_active = False
    await db.commit()
    return {"message": "已停用"}


@router.get("/admin/responses")
async def admin_list_responses(
    template_type: Optional[str] = None,
    keyword: Optional[str] = None,
    offset: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    _=Depends(current_admin),
):
    """管理员：查看所有问卷提交记录"""
    query = select(SurveyResponse).order_by(SurveyResponse.created_at.desc())
    if template_type:
        query = query.where(SurveyResponse.template_type == template_type)
    if keyword:
        kw = f"%{keyword}%"
        query = query.where(
            (SurveyResponse.user_name.like(kw)) | (SurveyResponse.user_phone.like(kw))
        )

    result = await db.execute(query.offset(offset).limit(limit))
    responses = result.scalars().all()

    return [
        {
            "id": r.id,
            "template_type": r.template_type,
            "user_id": r.user_id,
            "user_name": r.user_name,
            "user_phone": r.user_phone,
            "submitted_at": r.submitted_at,
            "total_score": r.total_score,
            "analysis": r.analysis,
            "answers": json.loads(r.answers) if r.answers else {},
            "created_at": str(r.created_at),
        }
        for r in responses
    ]


@router.get("/admin/responses/{response_id}")
async def admin_get_response_detail(
    response_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(current_admin),
):
    """管理员：查看问卷提交详情"""
    result = await db.execute(
        select(SurveyResponse).where(SurveyResponse.id == response_id)
    )
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="记录不存在")

    # 获取关联的模板（用于显示题目结构）
    t_result = await db.execute(
        select(SurveyTemplate).where(SurveyTemplate.id == r.template_id)
    )
    template = t_result.scalar_one_or_none()

    return {
        "id": r.id,
        "template_type": r.template_type,
        "template_name": template.name if template else "",
        "user_id": r.user_id,
        "user_name": r.user_name,
        "user_phone": r.user_phone,
        "submitted_at": r.submitted_at,
        "total_score": r.total_score,
        "analysis": r.analysis,
        "answers": json.loads(r.answers) if r.answers else {},
        "questions": json.loads(template.questions) if template and template.questions else [],
        "created_at": str(r.created_at),
    }
