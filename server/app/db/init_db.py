"""初始化脚本：开发种子数据与生产管理员引导。"""
import asyncio

from sqlalchemy import select

from app.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal, init_db
from app.models import KnowledgeArticle, MushroomRisk, User
from app.models.base import Base
import json


async def ensure_production_admin(db) -> User:
    """在空生产库中创建一次性引导管理员，绝不使用演示密码。"""
    existing = (
        await db.execute(
            select(User).where(User.role == "admin", User.is_active.is_(True)).limit(1)
        )
    ).scalar_one_or_none()
    if existing:
        return existing

    username = settings.admin_bootstrap_username.strip()
    password = settings.admin_bootstrap_password
    if not username or not password:
        raise RuntimeError(
            "生产数据库尚无管理员，请配置 ADMIN_BOOTSTRAP_USERNAME 与 "
            "ADMIN_BOOTSTRAP_PASSWORD 后重新部署"
        )

    collision = (
        await db.execute(select(User).where(User.username == username).limit(1))
    ).scalar_one_or_none()
    if collision:
        raise RuntimeError("ADMIN_BOOTSTRAP_USERNAME 已被其他账号占用")

    admin = User(
        role="admin",
        username=username,
        password_hash=hash_password(password),
        nickname="系统管理员",
        real_name="系统管理员",
        is_active=True,
    )
    db.add(admin)
    await db.commit()
    await db.refresh(admin)
    return admin


async def seed() -> None:
    # 先确保所有表都已 import（关键：chat 模型要进 Base.metadata）
    from app.models import chat, knowledge, meal, user, survey  # noqa: F401
    from app.models.survey import SurveyTemplate
    # 强制 Base.metadata 知道所有表
    _ = Base.metadata.tables
    # 生产环境的表结构必须先由 `alembic upgrade head` 创建；这里仅做
    # 首个管理员引导，避免 create_all 绕过迁移版本控制。
    if settings.app_env == "production":
        async with SessionLocal() as db:
            await ensure_production_admin(db)
        return

    await init_db()

    async with SessionLocal() as db:
        # 检查是否已有问卷模板，避免重复插入
        from sqlalchemy import select
        existing = (await db.execute(select(SurveyTemplate))).scalars().first()
        if not existing:
            # ══════════════════════════════════════════════════════════
            # 问卷模板 1：体重管理门诊基本信息表（病历首页）
            # 来自「0-体重管理门诊就诊信息登记表5.9.docx」+ 病历首页
            # ══════════════════════════════════════════════════════════
            basic_info_questions = [
                # ── step 0：基本信息 ──
                {"id": "bi1", "step": 0, "type": "input", "title": "登记号", "placeholder": "由医院分配，可留空"},
                {"id": "bi2", "step": 0, "type": "input", "title": "姓名", "placeholder": "请输入真实姓名"},
                {"id": "bi3", "step": 0, "type": "radio", "title": "性别", "options": ["男", "女"]},
                {"id": "bi4", "step": 0, "type": "input", "title": "年龄（岁）", "placeholder": "请输入年龄", "inputType": "number"},
                {"id": "bi5", "step": 0, "type": "input", "title": "身高（cm）", "placeholder": "请输入身高", "inputType": "number"},
                {"id": "bi6", "step": 0, "type": "input", "title": "联系电话", "placeholder": "请输入手机号", "inputType": "number"},
                {"id": "bi7", "step": 0, "type": "input", "title": "职业", "placeholder": "如：教师、工程师、退休等"},
                # ── step 1：就诊信息 ──
                {"id": "bi8", "step": 1, "type": "input", "title": "就诊日期", "placeholder": "如：2026-09-11"},
                {"id": "bi9", "step": 1, "type": "input", "title": "首诊医生", "placeholder": "由医生填写，可留空"},
                {"id": "bi10", "step": 1, "type": "textarea", "title": "体重管理主诉（就诊原因）", "placeholder": "请描述您来就诊的主要原因"},
                {"id": "bi11", "step": 1, "type": "textarea", "title": "现病史和用药史", "placeholder": "请描述目前疾病及正在服用的药物"},
                {"id": "bi12", "step": 1, "type": "textarea", "title": "食物特殊史（过敏、偏好等）", "placeholder": "如食物过敏、不耐受、特殊饮食偏好"},
                {"id": "bi13", "step": 1, "type": "textarea", "title": "过去体重管理史", "placeholder": "曾尝试过的减重方式、时间、效果等"},
                # ── step 2：体格检查（医生填写，可由患者先记录） ──
                {"id": "bi14", "step": 2, "type": "input", "title": "体重（kg）", "placeholder": "请输入体重", "inputType": "number"},
                {"id": "bi15", "step": 2, "type": "input", "title": "BMI（kg/m²）", "placeholder": "可由身高体重自动计算", "inputType": "number"},
                {"id": "bi16", "step": 2, "type": "input", "title": "体脂百分比（%）", "placeholder": "由体成分仪测量", "inputType": "number"},
                {"id": "bi17", "step": 2, "type": "input", "title": "内脏脂肪面积（cm²）", "placeholder": "由体成分仪测量", "inputType": "number"},
                {"id": "bi18", "step": 2, "type": "input", "title": "腰围（cm）", "placeholder": "请测量腰围", "inputType": "number"},
                {"id": "bi19", "step": 2, "type": "input", "title": "腰臀比", "placeholder": "腰围÷臀围", "inputType": "number"},
                {"id": "bi20", "step": 2, "type": "input", "title": "小腿围（cm）", "placeholder": "请测量小腿围", "inputType": "number"},
                {"id": "bi21", "step": 2, "type": "input", "title": "握力（kg）", "placeholder": "由握力器测量", "inputType": "number"},
                {"id": "bi22", "step": 2, "type": "textarea", "title": "备注", "placeholder": "其他需要说明的情况"},
            ]

            # ══════════════════════════════════════════════════════════
            # 问卷模板 2：体重管理门诊首诊评估表
            # 来自「3-体重管理门诊首诊+复诊全套表格.docx」首诊部分
            # ══════════════════════════════════════════════════════════
            first_visit_questions = [
                # ── step 0：动机与目标 ──
                {"id": "fv1", "step": 0, "type": "checkbox", "title": "您希望完成（可多选）", "options": ["减重", "增重", "增肌", "减脂"]},
                {"id": "fv2", "step": 0, "type": "radio", "title": "最主要的动机是", "options": ["健康需求", "提高自我形象需求", "生育需求", "医生建议"]},
                {"id": "fv3", "step": 0, "type": "input", "title": "其他动机（如有）", "placeholder": "可留空"},
                {"id": "fv4", "step": 0, "type": "textarea", "title": "您的目标", "placeholder": "请描述您的体重管理目标"},
                {"id": "fv5", "step": 0, "type": "radio", "title": "希望完成的时间", "options": ["1个月", "3个月", "6个月", "12个月"]},
                {"id": "fv6", "step": 0, "type": "input", "title": "其他时长（如有）", "placeholder": "可留空"},
                # ── step 1：体重管理经历 ──
                {"id": "fv7", "step": 1, "type": "radio", "title": "是否有过体重管理经历", "options": ["有", "无"]},
                {"id": "fv8", "step": 1, "type": "checkbox", "title": "曾尝试的方法（可多选）", "options": ["饮食", "运动", "药物", "其他"]},
                {"id": "fv9", "step": 1, "type": "input", "title": "曾用药物名称（如有）", "placeholder": "可留空"},
                {"id": "fv10", "step": 1, "type": "input", "title": "其他方法（如有）", "placeholder": "可留空"},
                {"id": "fv11", "step": 1, "type": "radio", "title": "效果是否达到预期", "options": ["是", "否"]},
                {"id": "fv12", "step": 1, "type": "checkbox", "title": "未达到预期的主要原因（可多选）", "options": ["难以坚持", "运动不足", "代谢问题", "其他"]},
                {"id": "fv13", "step": 1, "type": "input", "title": "其他原因（如有）", "placeholder": "可留空"},
                # ── step 2：健康与病史 ──
                {"id": "fv14", "step": 2, "type": "checkbox", "title": "您是否患有以下疾病（可多选）", "options": ["高血糖（糖尿病）", "高血压", "高血脂（脂肪肝）", "高尿酸（痛风）", "甲状腺疾病", "多囊卵巢综合征", "心理疾病", "其他"]},
                {"id": "fv15", "step": 2, "type": "textarea", "title": "用药情况", "placeholder": "请列出您服用的药物名称及剂量"},
                {"id": "fv16", "step": 2, "type": "checkbox", "title": "直系亲属是否有以下症状或疾病（可多选）", "options": ["肥胖", "消瘦", "糖尿病", "心血管疾病（高血压、高血脂、冠心病等）", "痛风", "甲状腺疾病", "无"]},
                {"id": "fv17", "step": 2, "type": "input", "title": "其他家族史（如有）", "placeholder": "可留空"},
                # ── step 3：饮食习惯 ──
                {"id": "fv18", "step": 3, "type": "radio", "title": "三餐是否规律", "options": ["是", "否"]},
                {"id": "fv19", "step": 3, "type": "radio", "title": "每餐平均就餐时长", "options": ["<15分钟", "15~30分钟", ">30分钟"]},
                {"id": "fv20", "step": 3, "type": "radio", "title": "饮食结构", "options": ["荤食为主", "素食为主", "荤素平衡"]},
                {"id": "fv21", "step": 3, "type": "radio", "title": "盐口味偏好", "options": ["非常清淡", "较清淡", "一般", "较重口味", "非常重口味"]},
                {"id": "fv22", "step": 3, "type": "radio", "title": "油口味偏好", "options": ["非常清淡", "较清淡", "一般", "较重口味", "非常重口味"]},
                {"id": "fv23", "step": 3, "type": "radio", "title": "辣度偏好", "options": ["非常清淡", "较清淡", "一般", "较重口味", "非常重口味"]},
                {"id": "fv24", "step": 3, "type": "radio", "title": "是否有吃零食（正餐之外的加餐）习惯", "options": ["是", "否（跳下一题）"]},
                {"id": "fv25", "step": 3, "type": "radio", "title": "吃零食的频率", "options": ["≥4次/周", "2~3次/周", "<1次/周"]},
                {"id": "fv26", "step": 3, "type": "input", "title": "最喜欢吃的零食（写三种）", "placeholder": "如：薯片、巧克力、坚果"},
                {"id": "fv27", "step": 3, "type": "radio", "title": "是否喝含糖饮料（可乐、果汁、奶茶等甜味饮品）", "options": ["是", "否（跳下一题）"]},
                {"id": "fv28", "step": 3, "type": "radio", "title": "含糖饮料摄入频率", "options": ["≥4次/周", "2~3次/周", "<1次/周"]},
                {"id": "fv29", "step": 3, "type": "radio", "title": "最近一个月在外就餐（含外卖）的频率", "options": [">10次/周", "5~9次/周", "1~4次/周", "几乎不"]},
                {"id": "fv30", "step": 3, "type": "radio", "title": "暴食暴饮的频率", "options": ["经常", "偶尔", "几乎不"]},
                {"id": "fv31", "step": 3, "type": "radio", "title": "饮酒情况", "options": ["每天喝酒", "经常喝酒", "有时喝酒", "极少喝酒", "完全不喝酒"]},
                {"id": "fv32", "step": 3, "type": "input", "title": "若喝酒，一般喝什么（白酒、红酒、啤酒等）", "placeholder": "可留空"},
                {"id": "fv33", "step": 3, "type": "input", "title": "平均每次大概喝酒（ml）", "placeholder": "可留空", "inputType": "number"},
                {"id": "fv34", "step": 3, "type": "radio", "title": "您过去一周内平均每天喝了多少杯水（1杯=200ml）", "options": ["≥7-8杯", "5-6杯", "3-4杯", "1-2杯", "不知道"]},
                # ── step 4：运动习惯 ──
                {"id": "fv35", "step": 4, "type": "radio", "title": "过去一个月，每周累计户外运动超过30分钟的天数", "options": ["每天", "5-7天", "3-4天", "1-2天", "不运动"]},
                {"id": "fv36", "step": 4, "type": "checkbox", "title": "主要户外运动（可多选）", "options": ["步行", "慢跑", "健身操", "游泳", "球类运动", "运动操"]},
                {"id": "fv37", "step": 4, "type": "input", "title": "其他运动（如有）", "placeholder": "可留空"},
                # ── step 5：睡眠情况 ──
                {"id": "fv38", "step": 5, "type": "radio", "title": "您最近2周自我感觉睡眠情况如何", "options": ["好", "一般", "差（如失眠、早醒）"]},
                {"id": "fv39", "step": 5, "type": "input", "title": "您晚上通常几时几分睡觉（24小时制）", "placeholder": "如：23:30"},
                {"id": "fv40", "step": 5, "type": "radio", "title": "平均每日睡眠时长（不含午休）", "options": ["<6小时", "6-7小时", "7-8小时", "≥8小时"]},
                {"id": "fv41", "step": 5, "type": "radio", "title": "最近一个月您使用助眠药情况", "options": ["无", "<1次/周", "1-2次/周", "≥3次/周"]},
            ]

            # ══════════════════════════════════════════════════════════
            # 问卷模板 3：体重管理防肥分数自测表（36 题是/否）
            # ══════════════════════════════════════════════════════════
            anti_obesity_questions = [
                # 一、有关饮品
                {"id": "ao1", "step": 0, "type": "radio", "title": "不喝甜饮料和奶茶等甜味饮品，用白水、淡茶水、淡柠檬水等替代", "options": ["是", "否"]},
                {"id": "ao2", "step": 0, "type": "radio", "title": "喝粥、汤、羹、豆浆、牛奶等，只喝原味，不加糖", "options": ["是", "否"]},
                {"id": "ao3", "step": 0, "type": "radio", "title": "不喝有添加脂肪的汤羹和饮品，如喝汤要去油", "options": ["是", "否"]},
                # 二、有关主食
                {"id": "ao4", "step": 1, "type": "radio", "title": "每天把至少一种全谷/杂豆食材纳入主食。如早上用牛奶燕麦粥替代白米粥", "options": ["是", "否"]},
                {"id": "ao5", "step": 1, "type": "radio", "title": "尽量不吃加了油/盐/糖的主食和小吃，如烧饼、油酥饼、油条、玉米烙、炒粉等", "options": ["是", "否"]},
                {"id": "ao6", "step": 1, "type": "radio", "title": "吃土豆、山药、蒸藕等含淀粉蔬菜时要替代一部分主食，而不是额外当菜吃", "options": ["是", "否"]},
                {"id": "ao7", "step": 1, "type": "radio", "title": "晚上一定要吃主食，避免夜间失眠。减重基本完成后，每日主食量（粮食干重）不低于 200 克", "options": ["是", "否"]},
                # 三、有关蔬菜
                {"id": "ao8", "step": 2, "type": "radio", "title": "每餐都吃 1 碗的少油烹调蔬菜（烹熟后）", "options": ["是", "否"]},
                {"id": "ao9", "step": 2, "type": "radio", "title": "每天都吃至少 1 碗的绿叶蔬菜（烹熟后）", "options": ["是", "否"]},
                {"id": "ao10", "step": 2, "type": "radio", "title": "尽量在早餐也吃少油烹调的蔬菜，如胡萝卜、烫青菜等", "options": ["是", "否"]},
                # 四、有关鱼肉蛋类
                {"id": "ao11", "step": 3, "type": "radio", "title": "每天早餐吃鸡蛋，优先选用嫩煮蛋、蒸蛋羹等少油烹调方式", "options": ["是", "否"]},
                {"id": "ao12", "step": 3, "type": "radio", "title": "尽量吃瘦肉，少吃肥牛、羊排、排骨等高脂肪部位，远离肥肉", "options": ["是", "否"]},
                {"id": "ao13", "step": 3, "type": "radio", "title": "吃鸡、鸭的时候，尽量去皮吃", "options": ["是", "否"]},
                # 五、有关烹调方式
                {"id": "ao14", "step": 4, "type": "radio", "title": "多用清蒸、白灼、水油焖等少油烹调法，避免油炸、油煎和肉丸", "options": ["是", "否"]},
                {"id": "ao15", "step": 4, "type": "radio", "title": "不喝有油的汤汁，少吃汤汁和米饭融合在一起的盖浇饭", "options": ["是", "否"]},
                {"id": "ao16", "step": 4, "type": "radio", "title": "如果不得不吃油多的菜肴，用热水涮涮油", "options": ["是", "否"]},
                # 六、有关甜食和冷饮
                {"id": "ao17", "step": 5, "type": "radio", "title": "用无糖或减糖酸奶替代甜食和冷饮", "options": ["是", "否"]},
                {"id": "ao18", "step": 5, "type": "radio", "title": "用水果替代零食，每天不超过 1 个苹果+ 1 个橙子的量", "options": ["是", "否"]},
                # 七、有关进食模式
                {"id": "ao19", "step": 6, "type": "radio", "title": "餐前喝 1-2 杯水", "options": ["是", "否"]},
                {"id": "ao20", "step": 6, "type": "radio", "title": "先吃半份蔬菜，再吃半份其他菜肴，最后吃主食", "options": ["是", "否"]},
                {"id": "ao21", "step": 6, "type": "radio", "title": "水果放在餐前吃，或至少用餐时吃，而不是吃完饭再吃", "options": ["是", "否"]},
                # 八、有关进食行为
                {"id": "ao22", "step": 7, "type": "radio", "title": "吃饭时专心体会食物带来的饱感，不看手机", "options": ["是", "否"]},
                {"id": "ao23", "step": 7, "type": "radio", "title": "晚餐尽量 6 点前吃完，晚餐后尽量不吃任何食物，争取每日 14 小时不进食", "options": ["是", "否"]},
                {"id": "ao24", "step": 7, "type": "radio", "title": "能找到自己合适的食量。以第二餐前不会饿得难受、睡前不会明显饥饿为准", "options": ["是", "否"]},
                {"id": "ao25", "step": 7, "type": "radio", "title": "偶尔一次吃多了不会感觉沮丧，下一餐少吃点，或者增加运动即可", "options": ["是", "否"]},
                # 九、有关日常活动和锻炼
                {"id": "ao26", "step": 8, "type": "radio", "title": "利用几分钟的时间走路、爬楼，如课间 10 分钟，开会前几分钟，取快递的几分钟等", "options": ["是", "否"]},
                {"id": "ao27", "step": 8, "type": "radio", "title": "收拾家居、清洗打扫等各种家务", "options": ["是", "否"]},
                {"id": "ao28", "step": 8, "type": "radio", "title": "在 3 公里以内的距离，把骑电动车改成骑自行车或走路", "options": ["是", "否"]},
                {"id": "ao29", "step": 8, "type": "radio", "title": "每周至少 2 次增肌运动，3 次有氧运动。周末尽量做到有 1 小时户外运动", "options": ["是", "否"]},
                # 十、有关休息
                {"id": "ao30", "step": 9, "type": "radio", "title": "晚 11 点之前睡觉", "options": ["是", "否"]},
                {"id": "ao31", "step": 9, "type": "radio", "title": "保持上床休息时间基本稳定，每天睡眠时间不低于 7 小时", "options": ["是", "否"]},
                {"id": "ao32", "step": 9, "type": "radio", "title": "学会放松心情，如果需要加班也按时睡下，同时上个闹钟，早上 6 点再起来工作效率更高", "options": ["是", "否"]},
                {"id": "ao33", "step": 9, "type": "radio", "title": "如果感觉特别累，这一天可以减少运动量，等精神好了再运动，不要把运动变成一种压力", "options": ["是", "否"]},
                # 十一、有关身体管理和自我感觉
                {"id": "ao34", "step": 10, "type": "radio", "title": "定期称体重（建议早上排空后空腹称重）", "options": ["是", "否"]},
                {"id": "ao35", "step": 10, "type": "radio", "title": "定期测量腰围（比称量体重更能反映体脂肪的变化）", "options": ["是", "否"]},
                {"id": "ao36", "step": 10, "type": "radio", "title": "注意衣服松紧程度的变化、体力的上升和面容气色的变化", "options": ["是", "否"]},
            ]

            # ══════════════════════════════════════════════════════════
            # 问卷模板 4：体重管理门诊复诊评估表
            # ══════════════════════════════════════════════════════════
            follow_up_questions = [
                # ── step 0：基础信息 ──
                {"id": "fu1", "step": 0, "type": "input", "title": "姓名", "placeholder": "请输入真实姓名"},
                {"id": "fu2", "step": 0, "type": "input", "title": "复诊日期", "placeholder": "如：2026-09-11"},
                {"id": "fu3", "step": 0, "type": "input", "title": "当前体重（kg）", "placeholder": "请输入今日体重", "inputType": "number"},
                {"id": "fu4", "step": 0, "type": "input", "title": "与上次相比体重变化（kg）", "placeholder": "正数增重，负数减重", "inputType": "number"},
                # ── step 1：饮食习惯 ──
                {"id": "fu5", "step": 1, "type": "radio", "title": "三餐是否规律", "options": ["是", "否"]},
                {"id": "fu6", "step": 1, "type": "radio", "title": "每餐平均就餐时长", "options": ["<15分钟", "15~30分钟", ">30分钟"]},
                {"id": "fu7", "step": 1, "type": "radio", "title": "饮食结构", "options": ["荤食为主", "素食为主", "荤素平衡"]},
                {"id": "fu8", "step": 1, "type": "radio", "title": "盐口味偏好", "options": ["非常清淡", "较清淡", "一般", "较重口味", "非常重口味"]},
                {"id": "fu9", "step": 1, "type": "radio", "title": "油口味偏好", "options": ["非常清淡", "较清淡", "一般", "较重口味", "非常重口味"]},
                {"id": "fu10", "step": 1, "type": "radio", "title": "辣度偏好", "options": ["非常清淡", "较清淡", "一般", "较重口味", "非常重口味"]},
                {"id": "fu11", "step": 1, "type": "radio", "title": "是否有吃零食（正餐之外的加餐）习惯", "options": ["是", "否（跳下一题）"]},
                {"id": "fu12", "step": 1, "type": "radio", "title": "吃零食的频率", "options": ["≥4次/周", "2~3次/周", "<1次/周"]},
                {"id": "fu13", "step": 1, "type": "input", "title": "最喜欢吃的零食（写三种）", "placeholder": "可留空"},
                {"id": "fu14", "step": 1, "type": "radio", "title": "是否喝含糖饮料（可乐、果汁、奶茶等甜味饮品）", "options": ["是", "否（跳下一题）"]},
                {"id": "fu15", "step": 1, "type": "radio", "title": "含糖饮料摄入频率", "options": ["≥4次/周", "2~3次/周", "<1次/周"]},
                {"id": "fu16", "step": 1, "type": "radio", "title": "最近一个月在外就餐（含外卖）的频率", "options": [">10次/周", "5~9次/周", "1~4次/周", "几乎不"]},
                {"id": "fu17", "step": 1, "type": "radio", "title": "暴食暴饮的频率", "options": ["经常", "偶尔", "几乎不"]},
                {"id": "fu18", "step": 1, "type": "radio", "title": "饮酒情况", "options": ["每天喝酒", "经常喝酒", "有时喝酒", "极少喝酒", "完全不喝酒"]},
                {"id": "fu19", "step": 1, "type": "input", "title": "若喝酒，一般喝什么", "placeholder": "可留空"},
                {"id": "fu20", "step": 1, "type": "input", "title": "平均每次喝酒量（ml）", "placeholder": "可留空", "inputType": "number"},
                {"id": "fu21", "step": 1, "type": "radio", "title": "您过去一周内平均每天喝多少杯水（1杯=200ml）", "options": ["≥7-8杯", "5-6杯", "3-4杯", "1-2杯", "不知道"]},
                # ── step 2：运动习惯 ──
                {"id": "fu22", "step": 2, "type": "radio", "title": "过去一个月，每周累计户外运动超过30分钟的天数", "options": ["每天", "5-7天", "3-4天", "1-2天", "不运动"]},
                {"id": "fu23", "step": 2, "type": "checkbox", "title": "主要户外运动（可多选）", "options": ["步行", "慢跑", "健身操", "游泳", "球类运动", "运动操"]},
                {"id": "fu24", "step": 2, "type": "input", "title": "其他运动（如有）", "placeholder": "可留空"},
                # ── step 3：睡眠情况 ──
                {"id": "fu25", "step": 3, "type": "radio", "title": "您最近2周自我感觉睡眠情况如何", "options": ["好", "一般", "差（如失眠、早醒）"]},
                {"id": "fu26", "step": 3, "type": "input", "title": "您晚上通常几时几分睡觉（24小时制）", "placeholder": "如：23:30"},
                {"id": "fu27", "step": 3, "type": "radio", "title": "平均每日睡眠时长（不含午休）", "options": ["<6小时", "6-7小时", "7-8小时", "≥8小时"]},
                {"id": "fu28", "step": 3, "type": "radio", "title": "最近一个月您使用助眠药情况", "options": ["无", "<1次/周", "1-2次/周", "≥3次/周"]},
                # ── step 4：体成分 ──
                {"id": "fu29", "step": 4, "type": "input", "title": "本次 BMI", "placeholder": "可由身高体重自动计算", "inputType": "number"},
                {"id": "fu30", "step": 4, "type": "input", "title": "本次体脂百分比（%）", "placeholder": "由体成分仪测量", "inputType": "number"},
                {"id": "fu31", "step": 4, "type": "input", "title": "本次腰围（cm）", "placeholder": "请测量腰围", "inputType": "number"},
                {"id": "fu32", "step": 4, "type": "textarea", "title": "其他需要说明的体成分指标", "placeholder": "可留空"},
            ]

            db.add(SurveyTemplate(
                type="weight_basic_info",
                name="体重管理门诊·基本信息表",
                description="体重管理门诊病历首页：人口学信息、主诉、用药史、体格检查",
                category="体重管理",
                questions=json.dumps(basic_info_questions, ensure_ascii=False),
                is_active=True,
                sort_order=1,
            ))
            db.add(SurveyTemplate(
                type="weight_clinic_first",
                name="体重管理门诊·首诊评估表",
                description="首次就诊评估：动机目标、减重经历、病史、饮食/运动/睡眠习惯",
                category="体重管理",
                questions=json.dumps(first_visit_questions, ensure_ascii=False),
                is_active=True,
                sort_order=2,
            ))
            db.add(SurveyTemplate(
                type="weight_anti_obesity",
                name="体重管理·防肥自测表",
                description="36 题评估您的日常防肥行为习惯，是/否作答",
                category="体重管理",
                questions=json.dumps(anti_obesity_questions, ensure_ascii=False),
                is_active=True,
                sort_order=3,
            ))
            db.add(SurveyTemplate(
                type="weight_clinic_follow",
                name="体重管理门诊·复诊评估表",
                description="复诊跟踪：体重变化、饮食/运动/睡眠执行情况、体成分",
                category="体重管理",
                questions=json.dumps(follow_up_questions, ensure_ascii=False),
                is_active=True,
                sort_order=4,
            ))

        db.add_all([
            KnowledgeArticle(
                category="guide",
                title="中国居民膳食指南（2022）核心要点",
                summary="食物多样、谷类为主，多吃蔬果、奶类、大豆，适量鱼禽蛋瘦肉，少盐少油。",
                content_html="<h3>核心推荐</h3><ul><li>每天 12 种以上食物</li><li>餐餐有蔬菜，天天有水果</li></ul>",
                source="国家卫生健康委",
                version=1,
            ),
            KnowledgeArticle(
                category="mushroom",
                title="川西常见毒蘑菇：鹅膏属",
                summary="含致命鹅膏毒素，主要分布于川西山区雨季。",
                content_html="<p>误食 6-24 小时后出现肝肾损害。</p>",
                source="四川省疾控中心",
                version=1,
            ),
        ])
        db.add_all([
            MushroomRisk(city="chengdu", name="都江堰山区", species="致命鹅膏", lat=30.99, lng=103.62, level="高", period="6-9 月", description="雨季高发，野外勿采勿食。"),
            MushroomRisk(city="chengdu", name="彭州白水河", species="黄盖鹅膏", lat=31.10, lng=103.83, level="中", period="7-8 月"),
        ])

        await db.commit()

        # 开发环境也不创建任何固定口令账号。确有管理端联调需要时，
        # 由开发者在本地 .env 显式设置一次性引导账号。
        if settings.admin_bootstrap_username and settings.admin_bootstrap_password:
            await ensure_production_admin(db)
        from app.db.survey_defaults import ensure_public_survey_templates
        await ensure_public_survey_templates(db)


if __name__ == "__main__":
    asyncio.run(seed())
    print("seed done")
