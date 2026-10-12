"""Independent source facts from the original two Word forms.

The golden statements below come from 3-体重管理门诊首诊+复诊全套表格.docx,
SHA256 6ec7891d4e4e258729cbb8895f1026ab4811decfb4cbeea7657f5c2a07488dc9.
They are deliberately independent of catalogue-building helpers and do not
require the private, gitignored Word files in CI.
"""
import re
import unicodedata

from app.db.survey_catalog import ORIGINAL_SURVEY_CATALOG


EXPECTED_ANTI_OBESITY_STATEMENTS = ['不喝甜饮料和奶茶等甜味饮品，用白水、淡茶水、淡柠檬水等替代',
 '喝粥、汤、羹、豆浆、牛奶等，只喝原味，不加糖',
 '不喝有添加脂肪的汤羹和饮品，如喝汤要去油',
 '每天把至少一种全谷/杂豆食材纳入主食。如早上用牛奶燕麦粥替代白米粥',
 '尽量不吃加了油/盐/糖的主食和小吃，如烧饼、油酥饼、油条、玉米烙、炒粉等',
 '吃土豆、山药、蒸藕等含淀粉蔬菜时要替代一部分主食，而不是额外当菜吃',
 '晚上一定要吃主食，避免夜间失眠。减重基本完成后，每日主食量（粮食干重）不低于 200 克',
 '每餐都吃 1 碗的少油烹调蔬菜（烹熟后）',
 '每天都吃至少 1 碗的绿叶蔬菜（烹熟后）',
 '尽量在早餐也吃少油烹调的蔬菜，如胡萝卜、烫青菜等',
 '每天早餐吃鸡蛋，优先选用嫩煮蛋、蒸蛋羹等少油烹调方式',
 '尽量吃瘦肉，少吃肥牛、羊排、排骨等高脂肪部位，远离肥肉',
 '吃鸡、鸭的时候，尽量去皮吃',
 '多用清蒸、白灼、水油焖等少油烹调法，避免油炸、油煎和肉丸',
 '不喝有油的汤汁，少吃汤汁和米饭融合在一起的盖浇饭',
 '如果不得不吃油多的菜肴，用热水涮涮油',
 '用无糖或减糖酸奶替代甜食和冷饮',
 '用水果替代零食，每天不超过 1 个苹果+ 1 个橙子的量',
 '餐前喝 1-2 杯水',
 '先吃半份蔬菜，再吃半份其他菜肴，最后吃主食',
 '水果放在餐前吃，或至少用餐时吃，而不是吃完饭再吃',
 '吃饭时专心体会食物带来的饱感，不看手机',
 '晚餐尽量 6点前吃完，晚餐后尽量不吃任何食物,争取每日14小时不进食',
 '能找到自己合适的食量。以第二餐前不会饿得难受、睡前不会明显饥饿为准',
 '偶尔一次吃多了不会感觉沮丧，下一餐少吃点，或者增加运动即可',
 '利用几分钟的时间走路、爬楼，如课间 10 分钟，开会前几分钟，取快递的几分钟等',
 '收拾家居、清洗打扫等各种家务',
 '在 3 公里以内的距离，把骑电动车改成骑自行车或走路',
 '每周至少 2 次增肌运动，3 次有氧运动。周末尽量做到有 1 小时户外运动',
 '晚 11 点之前睡觉',
 '保持上床休息时间基本稳定，每天睡眠时间不低于 7 小时',
 '学会放松心情，如果需要加班也按时睡下，同时上个闹钟，早上 6 点再起来工作效率更高',
 '如果感觉特别累，这一天可以减少运动量，等精神好了再运动，不要把运动变成一种压力',
 '定期称体重(建议早上排空后空腹称重)',
 '定期测量腰围（比称量体重更能反映体脂肪的变化）',
 '注意衣服松紧程度的变化、体力的上升和面容气色的变化']
EXPECTED_ANTI_OBESITY_SECTIONS = ['一、有关饮品',
 '二、有关主食',
 '三、有关蔬菜',
 '四、有关鱼肉蛋类',
 '五、有关烹调方式',
 '六、有关甜食和冷饮',
 '七、有关进食模式',
 '八、有关进食行为',
 '九、有关日常活动和锻炼',
 '十、有关休息',
 '十一、有关身体管理和自我感觉']


def normalized(value):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", value))


def catalogue():
    return {template["type"]: template for template in ORIGINAL_SURVEY_CATALOG}


def questions(template_type):
    return catalogue()[template_type]["questions"]


def question(template_type, title_fragment):
    matched = [item for item in questions(template_type)
               if normalized(title_fragment) in normalized(item["title"])]
    assert len(matched) == 1, (template_type, title_fragment, matched)
    return matched[0]


def test_original_catalogue_contains_five_distinct_forms_and_no_demo_substitution():
    assert set(catalogue()) == {
        "weight_visit_registration", "weight_basic_info", "weight_clinic_first",
        "weight_clinic_follow", "weight_anti_obesity",
    }
    assert len(ORIGINAL_SURVEY_CATALOG) == 5


def test_registration_preserves_all_ten_original_columns_in_order():
    assert [item["title"] for item in questions("weight_visit_registration")] == [
        "就诊日期", "登记号", "姓名", "性别", "年龄", "联系电话",
        "就诊诉求", "复诊日期", "接诊医生", "备注",
    ]


def test_anti_obesity_preserves_all_36_original_statements_in_order():
    items = questions("weight_anti_obesity")
    assert len(items) == 36
    assert [normalized(item["title"]) for item in items] == [
        normalized(statement) for statement in EXPECTED_ANTI_OBESITY_STATEMENTS
    ]
    assert len({item["id"] for item in items}) == 36
    assert all(item["type"] == "radio" and item["options"] == ["是", "否"] for item in items)
    assert list(dict.fromkeys(item["section"] for item in items)) == EXPECTED_ANTI_OBESITY_SECTIONS
    assert all(not {"score", "scores", "weight", "scoreMap", "scoring"}.intersection(item)
               for item in items), "The Word source supplies no scoring rules."


def test_first_and_follow_up_keep_original_lifestyle_options_in_order():
    for template_type in ("weight_clinic_first", "weight_clinic_follow"):
        for title_fragment, expected in [
            ("三餐是否规律", ["是", "否"]),
            ("每餐平均就餐时长", ["<15分钟", "15~30分钟", ">30分钟"]),
            ("饮食结构", ["荤食为主", "素食为主", "荤素平衡"]),
            ("在外就餐", [">10次/周", "5~9次/周", "1~4次/周", "几乎不"]),
            ("暴食暴饮", ["经常", "偶尔", "几乎不"]),
            ("饮酒情况", ["每天喝酒", "经常喝酒", "有时喝酒", "极少喝酒", "完全不喝酒"]),
            ("多少杯水", ["≥7-8杯", "5-6杯", "3-4杯", "1-2杯", "不知道"]),
            ("每周有几天", ["每天", "5-7天", "3-4天", "1-2天", "不运动"]),
            ("主要户外运动", ["步行", "慢跑", "健身操", "游泳", "球类运动", "运动操", "其他"]),
            ("平均每日睡眠时长", ["＜6小时", "6-7小时", "7-8小时", "≥8小时"]),
        ]:
            assert [normalized(option) for option in question(template_type, title_fragment)["options"]] == [
                normalized(option) for option in expected
            ], (template_type, title_fragment)
        for taste in ("盐", "油", "辣度"):
            matched = [item for item in questions(template_type)
                       if item["title"] == taste]
            assert len(matched) == 1, (template_type, taste)
            assert matched[0]["options"] == ["非常清淡", "较清淡", "一般", "较重口味", "非常重口味"]


def test_case_cover_preserves_all_original_fields_and_eight_measurements():
    assert [normalized(item["title"]) for item in questions("weight_basic_info")] == [
        normalized(title) for title in [
            "登记号", "姓名", "电话", "职业", "性别", "年龄", "身高",
            "体重管理主诉（就诊原因）", "现病史和用药史", "食物特殊史(过敏、偏好等)",
            "过去体重管理史", "日期", "体重(kg)", "BMI(kg/m2)", "体脂百分比",
            "内脏脂肪面积", "腰围", "腰臀比", "小腿围", "握力", "体成分检查（附打印结果）",
        ]
    ]
    assert question("weight_basic_info", "日期")["type"] == "date"
    for title in ("体重(kg)", "BMI(kg/m2)", "体脂百分比", "内脏脂肪面积", "腰围", "腰臀比", "小腿围", "握力"):
        assert question("weight_basic_info", title)["inputType"] == "digit"


def test_first_visit_preserves_original_goals_history_and_per_disease_medication():
    template_type = "weight_clinic_first"
    # Paper blanks for "other" and the eight disease-specific medication cells
    # become separate fields; no extra clinical conclusion is added.
    assert [normalized(item["title"]) for item in questions(template_type)] == [
        normalized(title) for title in [
            "你希望完成", "最主要的动机是", "其他", "目标", "希望完成的时间", "其他",
            "是否有过体重管理经历", "曾尝试的方法（可多选）", "药物", "其他",
            "效果是否达到预期？", "未达到预期的主要原因（可多选）", "其他",
            "是否有以下相关疾病及用药（可多选，在前面方框内打“√”）", "其他",
            *(["用药情况"] * 8), "直系亲属是否有以下症状或疾病（可多选）", "其他",
            "三餐是否规律", "每餐平均就餐时长", "饮食结构", "盐", "油", "辣度",
            "是否有吃零食（正餐之外的加餐）习惯？", "若是，吃零食的频率", "最喜欢吃的零食(写三种)",
            "是否喝含糖饮料（可乐、果汁、奶茶等甜味饮品）？", "若是，含糖饮料摄入频率？",
            "最近一个月在外就餐（含外卖）的频率", "暴食暴饮的频率", "饮酒情况",
            "如果喝酒，你一般喝", "其他", "平均每次大概喝酒",
            "您过去一周内平均每天喝了多少杯水（1杯=200ml）?",
            "过去一个月，您每周有几天累计户外运动时间超过30分钟（不包括上下班、买菜走路的运动时间）",
            "主要户外运动（可多选）", "其他", "您最近2周自我感觉睡眠情况如何",
            "您晚上通常几时几分睡觉（24小时制）", "平均每日睡眠时长(不含午休）", "最近一个月您使用助眠药情况",
        ]
    ]
    goal = question(template_type, "你希望完成")
    assert goal["type"] == "radio"
    assert goal["options"] == ["减重", "增重", "增肌", "减脂"]
    assert question(template_type, "最主要的动机")["options"] == [
        "健康需求", "提高自我形象需求", "生育需求", "医生建议", "其他",
    ]
    assert question(template_type, "希望完成的时间")["options"] == ["1个月", "3个月", "6个月", "12个月", "其他"]
    assert question(template_type, "是否有过体重管理经历")["options"] == ["有", "无"]
    assert question(template_type, "曾尝试的方法")["options"] == ["饮食", "运动", "药物", "其他"]
    assert question(template_type, "未达到预期的主要原因")["options"] == ["难以坚持", "运动不足", "代谢问题", "其他"]

    diseases = question(template_type, "是否有以下相关疾病及用药")
    assert diseases["type"] == "checkbox"
    assert diseases["options"] == [
        "高血糖（糖尿病）", "高血压", "高血脂（脂肪肝）", "高尿酸（痛风）",
        "甲状腺疾病", "多囊卵巢综合征", "心理疾病", "其他",
    ]
    medications = [item for item in questions(template_type) if item["title"] == "用药情况"]
    assert len(medications) == 8
    for disease in diseases["options"]:
        matching = [item for item in medications if item["showWhen"] == {
            "questionId": diseases["id"], "includes": disease,
        }]
        assert len(matching) == 1, disease
        assert disease in matching[0]["hint"]
    assert question(template_type, "直系亲属是否")["options"] == [
        "肥胖", "消瘦", "糖尿病", "心血管疾病（高血压、高血脂、冠心病等）",
        "痛风", "甲状腺疾病", "其他", "无",
    ]


def test_first_and_follow_up_preserve_skip_semantics_units_and_sleep_fields():
    for template_type in ("weight_clinic_first", "weight_clinic_follow"):
        snack_control = question(template_type, "是否有吃零食")
        assert snack_control["options"] == ["是", "否（跳16题）"]
        for fragment in ("吃零食的频率", "最喜欢吃的零食"):
            assert question(template_type, fragment)["showWhen"] == {
                "questionId": snack_control["id"], "equals": "是",
            }
        sugary_control = question(template_type, "是否喝含糖饮料")
        assert sugary_control["options"] == ["是", "否（跳18题）"]
        assert question(template_type, "含糖饮料摄入频率")["showWhen"] == {
            "questionId": sugary_control["id"], "equals": "是",
        }
        for fragment in ("吃零食的频率", "含糖饮料摄入频率"):
            assert question(template_type, fragment)["options"] == ["≥4次/周", "2~3次/周", "＜1次/周"]
        assert question(template_type, "平均每次大概喝酒")["unit"] == "ml"
        assert question(template_type, "多少杯水")["title"] == "您过去一周内平均每天喝了多少杯水（1杯=200ml）?"
        assert question(template_type, "最近2周自我感觉睡眠")["options"] == ["好", "一般", "差（如失眠、早醒）"]
        bedtime = question(template_type, "晚上通常几时几分睡觉")
        assert "24小时制" in bedtime["title"]
        assert bedtime.get("format") == "time" or bedtime["type"] == "time"
        assert question(template_type, "使用助眠药情况")["options"] == ["无", "<1次/周", "1-2次/周", "≥3次/周"]
        assert "暴饮暴食指在短时间内摄入远超正常进食量的食物" in question(template_type, "暴食暴饮")["hint"]


def test_original_forms_have_no_invented_scores_or_follow_up_questions():
    assert all(template.get("scoring") is None for template in ORIGINAL_SURVEY_CATALOG)
    follow_up = questions("weight_clinic_follow")
    assert len(follow_up) == 26
    assert not any(item["title"] in {"姓名", "联系电话", "本次体重", "体重变化", "目标达成率"}
                   for item in follow_up)
    assert follow_up[-1]["title"] == "体成分检查（附打印结果）"
