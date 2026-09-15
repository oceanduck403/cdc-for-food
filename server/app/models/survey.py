"""体重管理门诊问卷模型"""
from sqlalchemy import String, Integer, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class SurveyTemplate(Base, TimestampMixin):
    """问卷模板 - 管理员创建/编辑/删除"""
    __tablename__ = "survey_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 问卷类型标识，如 "weight_clinic_first"（首诊）、"weight_clinic_follow"（复诊）
    type: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    # 显示名称，如 "体重管理门诊首诊表"
    name: Mapped[str] = mapped_column(String(128))
    # 简介
    description: Mapped[str] = mapped_column(String(256), default="")
    # 题目列表（JSON 格式）
    # 结构: [{"id": "q1", "step": 0, "type": "radio", "title": "姓名", "options": []}, ...]
    questions: Mapped[str] = mapped_column(Text, default="[]")
    # 关联科室/用途标签，如 "体重管理", "营养科"
    category: Mapped[str] = mapped_column(String(64), default="体重管理")
    # 是否启用
    is_active: Mapped[bool] = mapped_column(default=True)
    # 排序权重
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    # 关联提交记录
    responses: Mapped[list["SurveyResponse"]] = relationship(back_populates="template")


class SurveyResponse(Base, TimestampMixin):
    """问卷提交记录 - 患者填写"""
    __tablename__ = "survey_responses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("survey_templates.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    # 问卷类型（冗余，方便查询）
    template_type: Mapped[str] = mapped_column(String(64), index=True)
    # 填写人姓名（方便管理员查看）
    user_name: Mapped[str] = mapped_column(String(64), default="")
    # 填写人手机号
    user_phone: Mapped[str] = mapped_column(String(20), default="")
    # 提交时间
    submitted_at: Mapped[str] = mapped_column(String(64), default="")
    # 问卷总分
    total_score: Mapped[float] = mapped_column(default=0)
    # AI 分析结果（JSON 格式）
    analysis: Mapped[str] = mapped_column(Text, default="")
    # 问卷答案（JSON 格式）
    # 结构: {"q1": "answer1", "q2": ["option1", "option2"], ...}
    answers: Mapped[str] = mapped_column(Text, default="{}")

    # 关联
    template: Mapped["SurveyTemplate"] = relationship(back_populates="responses")
