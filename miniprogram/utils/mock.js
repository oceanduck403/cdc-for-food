// utils/mock.js
// 演示用静态数据。所有真实数据请求在 useMock=true 时由 request.js 自动 fallback 到这里。
// 仅用于本地 demo/UI 跑通。线上请关闭 useMock。

function delay(data, ms = 220) {
  return new Promise((resolve) => setTimeout(() => resolve(data), ms));
}

const profile = {
  age: 35,
  sex: 'male',
  heightCm: 175,
  weightKg: 70,
  activityLevel: 'light',
  healthNotes: '示例档案（演示数据，非真实用户）',
  nickname: '演示用户',
  updatedAt: '2026-07-30'
};

const todaySummary = {
  calories: 1280,
  target: 2200,
  protein: 62,
  fat: 48,
  carbs: 168
};

const knowledgeMap = {
  guide: {
    name: '膳食指南',
    items: [
      {
        id: 'g-001',
        title: '中国居民膳食指南（2022）核心推荐',
        summary: '食物多样，合理搭配；吃动平衡，健康体重；少盐少油，控糖限酒。'
      },
      {
        id: 'g-002',
        title: '每日蔬菜摄入建议 300~500g',
        summary: '深色蔬菜应占一半以上，搭配菌菇与海产品更有助于微量元素均衡。'
      },
      {
        id: 'g-003',
        title: '主食怎么选？',
        summary: '建议全谷物与杂豆占三分之一，避免长期精白米面单一来源。'
      }
    ]
  },
  mushroom: {
    name: '毒蘑菇',
    items: [
      {
        id: 'm-001',
        title: '致命鹅膏（Amanita exitialis）',
        summary: '剧毒，主要分布于华南、西南山区。误食一朵即可致命。'
      },
      {
        id: 'm-002',
        title: '假褐云斑鹅膏',
        summary: '近年成都地区中毒事件的主要毒蘑菇种类之一。'
      },
      {
        id: 'm-003',
        title: '如何辨别毒蘑菇？',
        summary: '不存在"以颜色、是否生虫、银针变黑"等民间鉴别方法，靠谱做法是不采不食野生菌。'
      }
    ]
  },
  safety: {
    name: '食品安全',
    items: [
      {
        id: 's-001',
        title: '家庭食物储存 5 大原则',
        summary: '生熟分开、烧熟煮透、温度控制、清洗充分、查看保质期。'
      },
      {
        id: 's-002',
        title: '剩饭剩菜的正确处理',
        summary: '剩菜不要在室温下超过 2 小时；再次食用前需要彻底加热。'
      }
    ]
  },
  disease: {
    name: '食源性疾病',
    items: [
      {
        id: 'd-001',
        title: '沙门氏菌感染',
        summary: '夏季高发，多见于禽蛋与生冷肉制品。主要症状为发热、腹泻。'
      },
      {
        id: 'd-002',
        title: '副溶血性弧菌',
        summary: '与海产品、凉拌菜相关，沿海地区夏秋季多发。'
      }
    ]
  }
};

const knowledgeArticles = {
  'g-001': {
    id: 'g-001',
    title: '中国居民膳食指南（2022）核心推荐',
    source: '国家卫生健康委员会',
    updatedAt: '2026-07-30',
    contentHtml: `
      <h3 style="font-size:32rpx;font-weight:600;color:#0F2A1F;margin:24rpx 0 12rpx">一、食物多样，合理搭配</h3>
      <p style="line-height:1.7;color:#1F2D3D">每天的膳食应包括谷薯类、蔬菜水果、畜禽鱼蛋奶和豆类食物。平均每天摄入 12 种以上食物，每周 25 种以上。</p>
      <h3 style="font-size:32rpx;font-weight:600;color:#0F2A1F;margin:24rpx 0 12rpx">二、吃动平衡，健康体重</h3>
      <p style="line-height:1.7;color:#1F2D3D">各年龄段人群都应坚持日常身体活动，每周至少进行 5 天中等强度身体活动，累计 150 分钟以上。</p>
      <h3 style="font-size:32rpx;font-weight:600;color:#0F2A1F;margin:24rpx 0 12rpx">三、少盐少油，控糖限酒</h3>
      <p style="line-height:1.7;color:#1F2D3D">食盐每天不超过 5g，烹调油 25~30g，糖不超过 50g（最好 25g 以下）。</p>
    `
  },
  'm-001': {
    id: 'm-001',
    title: '致命鹅膏（Amanita exitialis）',
    source: '中国疾控中心',
    updatedAt: '2026-07-30',
    contentHtml: `
      <p style="line-height:1.7;color:#B91C1C;font-weight:600">⚠️ 剧毒菌类，误食一朵即可致命。</p>
      <h3 style="font-size:32rpx;font-weight:600;color:#0F2A1F;margin:24rpx 0 12rpx">主要特征</h3>
      <ul style="padding-left:40rpx;color:#1F2D3D">
        <li>菌盖白色，幼时卵形，成熟后平展</li>
        <li>菌柄基部有菌托（杯状结构）</li>
        <li>菌环（菌柄上的"小裙子"）白色</li>
      </ul>
      <h3 style="font-size:32rpx;font-weight:600;color:#0F2A1F;margin:24rpx 0 12rpx">中毒症状</h3>
      <p style="line-height:1.7;color:#1F2D3D">"假愈期"较长（6~12 小时），随后出现肝肾损伤。一旦怀疑误食，应立即就医，并保留剩余蘑菇作为鉴定依据。</p>
    `
  }
};

const mushroomMarkers = {
  items: [
    { id: 'mr-001', name: '龙泉山片区', lat: 30.5640, lng: 104.2780, level: '高', period: '6-9 月', species: '致命鹅膏' },
    { id: 'mr-002', name: '青城山片区', lat: 30.9050, lng: 103.5950, level: '中', period: '7-8 月', species: '假褐云斑鹅膏' },
    { id: 'mr-003', name: '彭州山区', lat: 30.9870, lng: 103.9480, level: '高', period: '6-8 月', species: '黄盖鹅膏' }
  ]
};

const mealAnalyzeResult = {
  mealId: 'demo-meal-001',
  items: [
    { name: '米饭', grams: 180, kcal: 234, protein: 4, fat: 0.6, carbs: 51 },
    { name: '番茄炒蛋', grams: 120, kcal: 168, protein: 11, fat: 11, carbs: 7 },
    { name: '清炒小白菜', grams: 100, kcal: 38, protein: 2, fat: 2, carbs: 3 }
  ]
};

const mealReport = {
  mealId: 'demo-meal-001',
  totalKcal: 440,
  protein: 17,
  fat: 13.6,
  carbs: 61,
  sodium: 480,
  structure: [
    { name: '碳水化合物', percent: 56 },
    { name: '脂肪', percent: 28 },
    { name: '蛋白质', percent: 16 }
  ],
  advice: [
    '蔬菜比例偏低，建议下一餐增加 100g 深色蔬菜。',
    '钠摄入接近每日参考值，注意少放调味品。',
    '主食结构合理，可继续以全谷物为主。'
  ]
};

const dailyQuota = { used: 2 };

module.exports = {
  delay,
  profile,
  todaySummary,
  knowledgeMap,
  knowledgeArticles,
  mushroomMarkers,
  mealAnalyzeResult,
  mealReport,
  dailyQuota
};
