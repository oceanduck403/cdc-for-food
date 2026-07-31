"""营养计算（BMR/TDEE + 建议生成）"""
from typing import Optional


def bmr_mifflin(sex: str, weight_kg: float, height_cm: float, age: int) -> float:
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age
    return base - 161 if sex == "female" else base + 5


def compute_tdee(
    sex: Optional[str],
    weight_kg: Optional[float],
    height_cm: Optional[float],
    age: Optional[int],
    activity_level: Optional[str],
) -> Optional[int]:
    if not all([sex, weight_kg, height_cm, age]):
        return None
    bmr = bmr_mifflin(sex, weight_kg, height_cm, age)
    factors = {
        "sedentary": 1.2,
        "light": 1.375,
        "moderate": 1.55,
        "active": 1.725,
    }
    factor = factors.get(activity_level or "", 1.2)
    return int(bmr * factor)


def generate_advice(kcal: float, protein: float, fat: float, carbs: float, sodium: float) -> list[str]:
    """基于本次摄入给出可执行的膳食建议"""
    advice: list[str] = []
    if kcal > 800:
        advice.append("本餐能量较高，建议下一餐以蔬菜和优质蛋白为主。")
    elif kcal < 300:
        advice.append("本餐能量偏低，注意主食摄入以维持血糖稳定。")
    else:
        advice.append("本餐能量适中，可继续保持均衡的膳食结构。")

    protein_pct = (protein * 4 / max(kcal, 1)) * 100
    if protein_pct < 15:
        advice.append("蛋白质占比偏低，可加一份鸡蛋、豆制品或牛奶。")
    elif protein_pct > 35:
        advice.append("蛋白质摄入偏高，注意搭配蔬菜减轻肾脏负担。")

    fat_pct = (fat * 9 / max(kcal, 1)) * 100
    if fat_pct > 40:
        advice.append("脂肪占比较高，下一餐建议清淡烹饪。")

    if sodium > 1500:
        advice.append("钠摄入偏高，注意减少咸菜、酱油等隐形盐。")

    advice.append("具体方案请结合个人健康档案并咨询专业营养师。")
    return advice