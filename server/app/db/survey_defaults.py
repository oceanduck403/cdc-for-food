"""按 Word 表头建立就诊登记模板；只新增，保留既有模板与填写记录。"""
import json

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.survey import SurveyTemplate

REGISTRATION_TYPE = "weight_visit_registration"
REGISTRATION_QUESTIONS = [
    {"id": "visit_date", "step": 0, "type": "date", "title": "就诊日期"},
    {"id": "registration_no", "step": 0, "type": "input", "title": "登记号", "placeholder": "由门诊填写，未分配可留空"},
    {"id": "name", "step": 0, "type": "input", "title": "姓名", "placeholder": "请输入姓名"},
    {"id": "sex", "step": 0, "type": "radio", "title": "性别", "options": ["男", "女"]},
    {"id": "age", "step": 0, "type": "input", "title": "年龄", "inputType": "number", "placeholder": "请输入年龄（岁）"},
    {"id": "phone", "step": 0, "type": "input", "title": "联系电话", "placeholder": "请输入手机号或固定电话"},
    {"id": "visit_request", "step": 1, "type": "textarea", "title": "就诊诉求", "placeholder": "请描述本次就诊希望解决的问题"},
    {"id": "follow_up_date", "step": 1, "type": "date", "title": "复诊日期", "placeholder": "尚未安排可留空"},
    {"id": "doctor", "step": 1, "type": "input", "title": "接诊医生", "placeholder": "请输入接诊医生姓名，未知可留空"},
    {"id": "notes", "step": 1, "type": "textarea", "title": "备注", "placeholder": "其他需要说明的情况，可留空"},
]


async def ensure_registration_template(db: AsyncSession) -> None:
    existing = await db.scalar(select(SurveyTemplate).where(SurveyTemplate.type == REGISTRATION_TYPE))
    if existing is not None:
        return
    db.add(SurveyTemplate(
        type=REGISTRATION_TYPE,
        name="体重管理门诊就诊信息登记表",
        description="就诊登记：基本资料、联系电话、就诊诉求、复诊安排及接诊医生",
        category="体重管理",
        questions=json.dumps(REGISTRATION_QUESTIONS, ensure_ascii=False),
        is_active=True,
        sort_order=0,
    ))
    try:
        await db.commit()
    except IntegrityError:
        # 多 worker 同时启动时，模板类型的唯一约束保证只插入一次。
        await db.rollback()
        if await db.scalar(select(SurveyTemplate.id).where(SurveyTemplate.type == REGISTRATION_TYPE)) is None:
            raise
