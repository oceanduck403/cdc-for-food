// utils/nutrition.js
// 仅做本地兜底的卡路里/Macronutrient 计算，权威营养数据来自 server 端 nutrition_service
function bmrMifflin({ sex, weightKg, heightCm, age }) {
  const base = 10 * weightKg + 6.25 * heightCm - 5 * age;
  return sex === 'female' ? base - 161 : base + 5;
}

function tdee(bmr, activityLevel) {
  const factors = {
    sedentary: 1.2,
    light: 1.375,
    moderate: 1.55,
    active: 1.725
  };
  return Math.round(bmr * (factors[activityLevel] || 1.2));
}

module.exports = { bmrMifflin, tdee };