// utils/qwen.js
// 阿里云百炼（千问 VL）图像识别封装
// 支持：菜品检测、食物分割、营养素估算
// 第三方服务密钥只保存在服务端；客户端通过登录态调用自有后端。
const { request } = require('./request.js');

// ─── 营养素数据库（常见食材，每 100g）───────────────────────────────
const NUTRI_DB = {
  米饭:        { kcal: 130, protein: 2.7, fat: 0.3,  carbs: 28.2 },
  白米饭:      { kcal: 130, protein: 2.7, fat: 0.3,  carbs: 28.2 },
  面条:        { kcal: 285, protein: 8.3, fat: 0.8,  carbs: 59.5 },
  馒头:        { kcal: 223, protein: 7.0, fat: 1.1,  carbs: 47.0 },
  包子:        { kcal: 227, protein: 9.1, fat: 5.7,  carbs: 36.2 },
  饺子:        { kcal: 242, protein: 9.5, fat: 9.0,  carbs: 30.8 },
  煎饼:        { kcal: 298, protein: 7.5, fat: 10.0, carbs: 45.0 },
  油条:        { kcal: 386, protein: 6.9, fat: 17.6, carbs: 50.0 },
  面包:        { kcal: 265, protein: 8.0, fat: 3.2,  carbs: 50.0 },
  鸡蛋:        { kcal: 144, protein: 13.3, fat: 9.8, carbs: 1.5  },
  煮鸡蛋:      { kcal: 144, protein: 13.3, fat: 9.8, carbs: 1.5  },
  煎鸡蛋:      { kcal: 199, protein: 13.3, fat: 15.5, carbs: 1.5  },
  西红柿炒鸡蛋: { kcal: 140, protein: 9.5,  fat: 9.2,  carbs: 7.0  },
  番茄炒蛋:     { kcal: 140, protein: 9.5,  fat: 9.2,  carbs: 7.0  },
  炒鸡蛋:      { kcal: 180, protein: 11.0, fat: 14.0, carbs: 3.0  },
  鸡肉:        { kcal: 167, protein: 31.0, fat: 3.6,  carbs: 0    },
  鸡腿:        { kcal: 181, protein: 28.3, fat: 6.7,  carbs: 0    },
  鸡翅:        { kcal: 203, protein: 26.4, fat: 10.4, carbs: 0    },
  炸鸡:        { kcal: 298, protein: 24.0, fat: 18.0, carbs: 8.0  },
  猪肉:        { kcal: 143, protein: 21.3, fat: 6.2,  carbs: 0    },
  瘦肉:        { kcal: 143, protein: 21.3, fat: 6.2,  carbs: 0    },
  五花肉:      { kcal: 395, protein: 13.2, fat: 37.0, carbs: 0    },
  排骨:        { kcal: 278, protein: 20.4, fat: 21.0, carbs: 0    },
  红烧肉:      { kcal: 478, protein: 13.0, fat: 43.0, carbs: 9.0  },
  牛肉:        { kcal: 125, protein: 22.3, fat: 3.4,  carbs: 0    },
  牛排:        { kcal: 271, protein: 26.0, fat: 17.5, carbs: 0    },
  羊肉:        { kcal: 143, protein: 23.0, fat: 4.0,  carbs: 0    },
  鱼肉:        { kcal: 90,  protein: 18.0, fat: 2.0,  carbs: 0    },
  清蒸鱼:      { kcal: 98,  protein: 18.5, fat: 2.5,  carbs: 0    },
  红烧鱼:      { kcal: 145, protein: 16.0, fat: 7.0,  carbs: 3.0  },
  虾:          { kcal: 85,  protein: 20.0, fat: 0.5,  carbs: 0    },
  白灼虾:      { kcal: 85,  protein: 20.0, fat: 0.5,  carbs: 0    },
  虾仁:        { kcal: 90,  protein: 22.0, fat: 0.6,  carbs: 0    },
  蟹:          { kcal: 97,  protein: 18.0, fat: 1.2,  carbs: 0    },
  青菜:        { kcal: 14,  protein: 1.5,  fat: 0.2,  carbs: 2.4  },
  小白菜:      { kcal: 17,  protein: 1.7,  fat: 0.2,  carbs: 3.2  },
  菠菜:        { kcal: 20,  protein: 2.4,  fat: 0.2,  carbs: 3.0  },
  生菜:        { kcal: 15,  protein: 1.4,  fat: 0.2,  carbs: 2.9  },
  菜心:        { kcal: 19,  protein: 2.0,  fat: 0.3,  carbs: 3.2  },
  油菜:        { kcal: 23,  protein: 2.0,  fat: 0.3,  carbs: 4.0  },
  大白菜:      { kcal: 18,  protein: 1.6,  fat: 0.1,  carbs: 3.3  },
  卷心菜:      { kcal: 24,  protein: 1.5,  fat: 0.1,  carbs: 5.8  },
  娃娃菜:      { kcal: 13,  protein: 1.2,  fat: 0.1,  carbs: 2.5  },
  莴笋:        { kcal: 15,  protein: 1.0,  fat: 0.1,  carbs: 3.2  },
  苦瓜:        { kcal: 18,  protein: 1.0,  fat: 0.2,  carbs: 4.2  },
  黄瓜:        { kcal: 15,  protein: 0.8,  fat: 0.2,  carbs: 3.6  },
  西红柿:      { kcal: 19,  protein: 0.9,  fat: 0.2,  carbs: 4.0  },
  番茄:        { kcal: 19,  protein: 0.9,  fat: 0.2,  carbs: 4.0  },
  土豆:        { kcal: 76,  protein: 2.0,  fat: 0.1,  carbs: 17.0 },
  土豆丝:      { kcal: 112, protein: 2.0, fat: 5.0,  carbs: 15.0 },
  茄子:        { kcal: 21,  protein: 1.0,  fat: 0.2,  carbs: 4.5  },
  豆角:        { kcal: 34,  protein: 2.5,  fat: 0.2,  carbs: 6.0  },
  四季豆:      { kcal: 34,  protein: 2.5,  fat: 0.2,  carbs: 6.0  },
  莲藕:        { kcal: 70,  protein: 1.9,  fat: 0.1,  carbs: 16.0 },
  木耳:        { kcal: 27,  protein: 1.5,  fat: 0.1,  carbs: 6.0  },
  香菇:        { kcal: 26,  protein: 2.7,  fat: 0.3,  carbs: 5.2  },
  蘑菇:        { kcal: 22,  protein: 2.5,  fat: 0.2,  carbs: 4.0  },
  金针菇:      { kcal: 22,  protein: 2.4,  fat: 0.2,  carbs: 3.8  },
  豆腐:        { kcal: 81,  protein: 8.0,  fat: 3.7,  carbs: 4.0  },
  麻婆豆腐:    { kcal: 135, protein: 9.0,  fat: 9.5,  carbs: 6.0  },
  豆浆:        { kcal: 33,  protein: 2.9,  fat: 1.2,  carbs: 3.0  },
  粥:          { kcal: 46,  protein: 1.1,  fat: 0.2,  carbs: 9.9  },
  小米粥:      { kcal: 46,  protein: 1.2,  fat: 0.2,  carbs: 9.6  },
  南瓜:        { kcal: 23,  protein: 0.7,  fat: 0.1,  carbs: 5.6  },
  玉米:        { kcal: 112, protein: 4.0,  fat: 1.2,  carbs: 22.8 },
  红薯:        { kcal: 99,  protein: 1.1,  fat: 0.1,  carbs: 24.7 },
  苹果:        { kcal: 52,  protein: 0.3,  fat: 0.2,  carbs: 13.7 },
  香蕉:        { kcal: 93,  protein: 1.4,  fat: 0.2,  carbs: 22.8 },
  橙子:        { kcal: 47,  protein: 0.9,  fat: 0.1,  carbs: 11.8 },
  葡萄:        { kcal: 67,  protein: 0.6,  fat: 0.2,  carbs: 17.3 },
  西瓜:        { kcal: 30,  protein: 0.6,  fat: 0.1,  carbs: 7.9  },
  牛奶:        { kcal: 54,  protein: 3.0,  fat: 2.9,  carbs: 3.4  },
  酸奶:        { kcal: 72,  protein: 2.9,  fat: 2.7,  carbs: 9.3  },
  蛋糕:        { kcal: 374, protein: 5.2,  fat: 13.0, carbs: 58.0 },
  饼干:        { kcal: 435, protein: 5.4,  fat: 14.0, carbs: 72.0 },
  薯片:        { kcal: 548, protein: 4.0,  fat: 37.0, carbs: 50.0 },
  奶茶:        { kcal: 78,  protein: 0.8,  fat: 1.8,  carbs: 14.5 },
  可乐:        { kcal: 42,  protein: 0,   fat: 0,    carbs: 10.6 },
  汤:          { kcal: 30,  protein: 2.0,  fat: 1.5,  carbs: 2.0  },
  紫菜蛋花汤:  { kcal: 28,  protein: 2.2,  fat: 1.4,  carbs: 1.8  },
  蛋花汤:      { kcal: 35,  protein: 2.5,  fat: 1.8,  carbs: 2.5  },
  番茄蛋汤:    { kcal: 32,  protein: 2.2,  fat: 1.5,  carbs: 3.0  },
  宫保鸡丁:    { kcal: 215, protein: 18.0, fat: 12.0, carbs: 8.0  },
  糖醋里脊:    { kcal: 235, protein: 15.0, fat: 11.0, carbs: 18.0 },
  鱼香肉丝:    { kcal: 195, protein: 14.0, fat: 10.0, carbs: 12.0 },
  回锅肉:      { kcal: 289, protein: 16.0, fat: 22.0, carbs: 5.0  },
  京酱肉丝:    { kcal: 260, protein: 16.0, fat: 18.0, carbs: 8.0  },
  辣子鸡:      { kcal: 228, protein: 20.0, fat: 14.0, carbs: 6.0  },
  毛血旺:      { kcal: 212, protein: 16.0, fat: 14.0, carbs: 5.0  },
  酸菜鱼:      { kcal: 148, protein: 20.0, fat: 6.0,  carbs: 4.0  },
  水煮鱼:      { kcal: 225, protein: 18.0, fat: 15.0, carbs: 4.0  },
  麻婆豆腐:    { kcal: 135, protein: 9.0,  fat: 9.5,  carbs: 6.0  },
  红烧茄子:    { kcal: 98,  protein: 2.5,  fat: 5.5,  carbs: 10.0 },
  炒时蔬:      { kcal: 35,  protein: 2.0,  fat: 1.5,  carbs: 4.5  },
  炒青菜:      { kcal: 30,  protein: 2.0,  fat: 1.5,  carbs: 3.5  },
  炒蔬菜:      { kcal: 35,  protein: 2.0,  fat: 1.5,  carbs: 4.5  },
  炒饭:        { kcal: 188, protein: 5.0,  fat: 7.0,  carbs: 28.0 },
  蛋炒饭:      { kcal: 198, protein: 6.0,  fat: 8.0,  carbs: 27.0 },
  炒面:        { kcal: 295, protein: 8.0,  fat: 12.0, carbs: 40.0 },
  凉面:        { kcal: 268, protein: 6.0,  fat: 11.0, carbs: 38.0 },
  凉皮:        { kcal: 138, protein: 3.0,  fat: 0.5,  carbs: 30.0 },
  火锅:        { kcal: 215, protein: 14.0, fat: 15.0, carbs: 8.0  },
  麻辣烫:      { kcal: 198, protein: 12.0, fat: 11.0, carbs: 14.0 },
  烤肉:        { kcal: 268, protein: 22.0, fat: 18.0, carbs: 2.0  },
  披萨:        { kcal: 266, protein: 11.0, fat: 10.0, carbs: 35.0 },
  汉堡:        { kcal: 295, protein: 13.0, fat: 14.0, carbs: 30.0 },
  薯条:        { kcal: 312, protein: 3.4,  fat: 15.0, carbs: 41.0 },
  炸薯条:      { kcal: 312, protein: 3.4,  fat: 15.0, carbs: 41.0 },
  炸鸡腿:      { kcal: 298, protein: 24.0, fat: 18.0, carbs: 8.0  },
  蒸蛋:        { kcal: 138, protein: 12.5, fat: 9.0,  carbs: 1.5  },
  鸡蛋羹:      { kcal: 138, protein: 12.5, fat: 9.0,  carbs: 1.5  },
  蒸鸡蛋羹:    { kcal: 138, protein: 12.5, fat: 9.0,  carbs: 1.5  },
  皮蛋瘦肉粥:  { kcal: 85,  protein: 4.5,  fat: 2.5,  carbs: 12.0 },
  皮蛋粥:      { kcal: 70,  protein: 3.0,  fat: 2.0,  carbs: 10.0 },
  馄饨:        { kcal: 212, protein: 9.5,  fat: 8.0,  carbs: 28.0 },
  烧麦:        { kcal: 238, protein: 8.5,  fat: 9.5,  carbs: 32.0 },
  汤圆:        { kcal: 280, protein: 5.0,  fat: 8.0,  carbs: 48.0 },
  春卷:        { kcal: 330, protein: 6.0,  fat: 16.0, carbs: 42.0 },
  卤肉饭:      { kcal: 285, protein: 12.0, fat: 11.0, carbs: 36.0 },
  盖浇饭:      { kcal: 268, protein: 8.0,  fat: 9.0,  carbs: 38.0 },
  咖喱饭:      { kcal: 245, protein: 7.5,  fat: 8.5,  carbs: 36.0 },
  炒河粉:      { kcal: 285, protein: 6.0,  fat: 12.0, carbs: 40.0 },
  煎饼果子:    { kcal: 298, protein: 8.0,  fat: 10.0, carbs: 45.0 },
  手抓饼:      { kcal: 312, protein: 6.0,  fat: 14.0, carbs: 42.0 },
  肉夹馍:      { kcal: 286, protein: 11.0, fat: 12.0, carbs: 34.0 },
  鸡蛋灌饼:    { kcal: 295, protein: 9.0,  fat: 12.0, carbs: 38.0 },
  莲藕排骨汤:  { kcal: 128, protein: 9.0,  fat: 8.0,  carbs: 6.0  },
  冬瓜排骨汤:  { kcal: 98,  protein: 8.0,  fat: 6.0,  carbs: 4.0  },
  玉米排骨汤:  { kcal: 112, protein: 9.5,  fat: 6.5,  carbs: 6.0  },
  丸子:        { kcal: 248, protein: 14.0, fat: 18.0, carbs: 6.0  },
  肉丸:        { kcal: 248, protein: 14.0, fat: 18.0, carbs: 6.0  },
  鱼丸:        { kcal: 98,  protein: 17.0, fat: 2.0,  carbs: 2.0  },
  粉丝:        { kcal: 335, protein: 0.8,  fat: 0.0,  carbs: 83.4 },
  粉条:        { kcal: 338, protein: 0.5,  fat: 0.0,  carbs: 84.2 },
  腐竹:        { kcal: 459, protein: 44.6, fat: 21.8, carbs: 22.3 },
  烤麸:        { kcal: 121, protein: 9.3,  fat: 3.3,  carbs: 16.2 },
  泡菜:        { kcal: 22,  protein: 1.1,  fat: 0.2,  carbs: 4.5  },
  酸菜:        { kcal: 19,  protein: 1.0,  fat: 0.2,  carbs: 4.0  },
  咸菜:        { kcal: 22,  protein: 1.2,  fat: 0.2,  carbs: 4.5  },
  凉拌黄瓜:    { kcal: 35,  protein: 1.0,  fat: 2.0,  carbs: 3.5  },
  凉拌木耳:    { kcal: 42,  protein: 1.5,  fat: 1.8,  carbs: 5.5  },
  凉拌豆腐:    { kcal: 78,  protein: 6.0,  fat: 4.5,  carbs: 4.0  },
  拍黄瓜:      { kcal: 35,  protein: 1.0,  fat: 2.0,  carbs: 3.5  },
  果蔬沙拉:    { kcal: 48,  protein: 1.5,  fat: 2.0,  carbs: 6.5  },
  沙拉:        { kcal: 65,  protein: 1.5,  fat: 4.0,  carbs: 6.0  },
  薯泥:        { kcal: 101, protein: 1.5,  fat: 3.8,  carbs: 16.0 },
  土豆泥:      { kcal: 101, protein: 1.5,  fat: 3.8,  carbs: 16.0 },
  牛油果:      { kcal: 160, protein: 2.0,  fat: 15.0, carbs: 9.0  },
  坚果:        { kcal: 607, protein: 20.0, fat: 54.0, carbs: 15.0 },
  花生:        { kcal: 589, protein: 24.8, fat: 44.3, carbs: 21.0 },
  腰果:        { kcal: 552, protein: 18.2, fat: 43.9, carbs: 30.2 },
  杏仁:        { kcal: 579, protein: 21.3, fat: 49.4, carbs: 19.7 },
  '饼干(甜)':   { kcal: 435, protein: 5.4,  fat: 14.0, carbs: 72.0 },
};

// ─── 核心函数 ─────────────────────────────────────────────────────

/**
 * 分析一张食物图片，返回营养数据列表
 * @param {string} imagePath - 小程序本地图片路径（wx.chooseMedia 返回的 tempFilePath）
 * @returns {Promise<Array>} 食物列表 [{ name, grams, kcal, protein, fat, carbs }]
 */
function analyzeMeal(imagePath) {
  return readBase64(imagePath).then(base64 => {
    return callQwenVL(base64);
  });
}

/**
 * 读取图片为 base64（小程序 wxfs.readFile）
 */
function readBase64(filePath) {
  return new Promise((resolve, reject) => {
    wx.getFileSystemManager().readFile({
      filePath,
      encoding: 'base64',
      success: res => resolve(res.data),
      fail: err => {
        console.error('[qwen] 读取图片失败', err);
        reject(new Error('读取图片失败'));
      }
    });
  });
}

/**
 * 调用千问 VL，返回原始 JSON（未加工）
 */
function callQwenVL(imageBase64) {
  return request({
    url: '/ai/food-analysis',
    method: 'POST',
    data: { imageBase64 },
    showLoading: false,
    silent: true
  });
}

/**
 * 从千问返回的文本中提取 JSON（支持 markdown 代码块和裸 JSON）
 */
function parseFoodsFromText(text) {
  let jsonStr = text.trim();

  // 去掉 markdown 代码块标记
  const codeBlockMatch = jsonStr.match(/```(?:json)?\s*([\s\S]*?)```/);
  if (codeBlockMatch) jsonStr = codeBlockMatch[1].trim();

  // 去掉可能的引导语（如"以下是 JSON："）
  const jsonStart = jsonStr.indexOf('{');
  if (jsonStart > 0) jsonStr = jsonStr.slice(jsonStart);

  return JSON.parse(jsonStr);
}

/**
 * 将千问返回的 foods 数组转换为营养数据格式
 * @param {Array} foods - 千问返回的 [{ name, grams }]
 * @returns {Array} [{ name, grams, kcal, protein, fat, carbs }]
 */
function enrichNutrition(foods) {
  return foods.map(item => {
    const name = item.name || '';
    const grams = Number(item.grams) || 100;
    const key = name in NUTRI_DB ? name : fuzzyMatch(name);
    const base = NUTRI_DB[key] || { kcal: 100, protein: 5, fat: 5, carbs: 15 };
    const factor = grams / 100;

    return {
      name,
      grams,
      kcal: Math.round(base.kcal * factor),
      protein: Math.round(base.protein * factor * 10) / 10,
      fat: Math.round(base.fat * factor * 10) / 10,
      carbs: Math.round(base.carbs * factor * 10) / 10
    };
  });
}

/**
 * 模糊匹配食物名称到营养库
 */
function fuzzyMatch(name) {
  for (const key of Object.keys(NUTRI_DB)) {
    if (name.includes(key) || key.includes(name)) return key;
  }
  return null;
}

// ─── 统一导出（capture.js 只调用这一个）────────────────────────────

/**
 * 主入口：输入图片路径 → 返回 AI 自然语言分析（识别+营养+建议）
 */
async function analyzeFoodFromImage(imagePath) {
  // 1. 调用千问识别图片中的食物
  const qwenResult = await analyzeMeal(imagePath);
  const foods = qwenResult.items || qwenResult.foods || [];

  if (foods.length === 0) {
    return {
      description: '未识别到食物，请尝试更清晰的图片。'
    };
  }

  // 2. 估算营养
  const items = qwenResult.items || enrichNutrition(foods);

  // 3. 生成自然语言描述：识别 + 营养 + 建议
  const names = items.map(item => item.name).join('、');
  let description = `🍱 识别食物：${names}\n\n`;

  // 主要营养（按食物给出，不显示具体重量热量）
  description += `🥗 主要营养：\n`;
  const nutritionMap = {};
  items.forEach(item => {
    // 简化标签，不显示重量和热量
    if (item.protein > 5) nutritionMap['蛋白质'] = true;
    if (item.carbs > 10) nutritionMap['碳水化合物'] = true;
    if (item.fat > 5) nutritionMap['脂肪'] = true;
    if (item.kcal < 50) nutritionMap['膳食纤维'] = true;
    if (item.kcal < 30 && item.protein < 3) nutritionMap['维生素/矿物质'] = true;
  });

  // 兜底
  if (Object.keys(nutritionMap).length === 0) {
    nutritionMap['综合营养'] = true;
  }
  description += Object.keys(nutritionMap).join('、') + '\n\n';

  // 营养评价 + 建议
  const hasVeggie = items.some(i =>
    ['青菜','小白菜','菠菜','生菜','菜心','油菜','大白菜','卷心菜','娃娃菜',
     '莴笋','苦瓜','黄瓜','西红柿','番茄','土豆','茄子','豆角','四季豆',
     '莲藕','木耳','香菇','蘑菇','金针菇','南瓜','玉米','红薯','凉拌黄瓜',
     '凉拌木耳','凉拌豆腐','拍黄瓜','果蔬沙拉'].includes(i.name)
  );
  const hasMeat = items.some(i =>
    ['鸡肉','鸡腿','鸡翅','炸鸡','猪肉','瘦肉','五花肉','排骨','红烧肉',
     '牛肉','牛排','羊肉','鱼肉','清蒸鱼','红烧鱼','虾','白灼虾','虾仁','蟹',
     '麻婆豆腐','红烧茄子','炒时蔬','炒青菜','炒蔬菜','烤麸','丸子','肉丸',
     '鱼丸','豆腐'].includes(i.name)
  );
  const hasStaple = items.some(i =>
    ['米饭','白米饭','面条','馒头','包子','饺子','煎饼','面包','粥','小米粥',
     '炒饭','蛋炒饭','炒面','凉面','凉皮','馄饨','烧麦','汤圆','卤肉饭','盖浇饭',
     '咖喱饭','炒河粉','煎饼果子','手抓饼','肉夹馍','鸡蛋灌饼'].includes(i.name)
  );
  const hasFried = items.some(i =>
    ['炸鸡','薯条','炸薯条','炸鸡腿','薯片','油条','春卷','蛋糕','饼干'].includes(i.name)
  );

  description += `💡 营养评价与建议：\n`;

  if (hasFried && !hasVeggie) {
    description += `这餐以油炸食品为主，建议搭配新鲜蔬菜水果一起食用，减少油炸摄入，多喝水。`;
  } else if (hasStaple && hasMeat && !hasVeggie) {
    description += `营养较丰富，但缺少蔬菜，建议增加一份青菜或水果，保持膳食均衡。`;
  } else if (hasMeat && hasVeggie) {
    description += `荤素搭配合理，蛋白质和膳食纤维都充足。继续保持均衡饮食的好习惯！`;
  } else if (hasVeggie && !hasMeat) {
    description += `蔬菜摄入充足，建议搭配优质蛋白（如鸡蛋、鱼肉、豆腐）一起食用。`;
  } else if (items.length === 1) {
    description += `这一餐较为单一，建议增加食物种类，搭配主食、蛋白质和蔬菜水果。`;
  } else {
    description += `整体搭配不错，建议细嚼慢咽，控制食量，搭配适量运动效果更好。`;
  }

  return {
    ...qwenResult,
    items,
    totalKcal: qwenResult.totalKcal || items.reduce((sum, item) => sum + (item.kcal || 0), 0),
    totalProtein: qwenResult.totalProtein || items.reduce((sum, item) => sum + (item.protein || 0), 0),
    totalFat: qwenResult.totalFat || items.reduce((sum, item) => sum + (item.fat || 0), 0),
    totalCarbs: qwenResult.totalCarbs || items.reduce((sum, item) => sum + (item.carbs || 0), 0),
    totalSodium: qwenResult.totalSodium || items.reduce((sum, item) => sum + (item.sodium || 0), 0),
    description
  };
}

module.exports = {
  analyzeFoodFromImage,
  analyzeMeal,
  callQwenVL,
  enrichNutrition,
  NUTRI_DB
};
