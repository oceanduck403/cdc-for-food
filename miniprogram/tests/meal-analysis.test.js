const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

test('拍照分析保留服务端 mealId，完整报告跳转到对应记录', async () => {
  let page;
  let opened = '';
  const app = { globalData: { dailyAnalysisCount: 0 } };
  const qwenResult = {
    mealId: 42,
    items: [{ name: '米饭', grams: 150, kcal: 195, protein: 4, fat: 0.5, carbs: 42, sodium: 3 }],
    totalKcal: 195,
    totalProtein: 4,
    totalFat: 0.5,
    totalCarbs: 42,
    totalSodium: 3,
  };
  const source = fs.readFileSync(path.join(__dirname, '../pages/capture/capture.js'), 'utf8');
  vm.runInNewContext(source, {
    Page: value => { page = value; },
    getApp: () => app,
    console,
    wx: { showToast() {} },
    require: request => {
      if (request.includes('navigation')) return { open: ({ url }) => { opened = url; } };
      if (request.includes('config')) return { dailyAnalysisLimit: 20 };
      if (request.includes('qwen')) return { analyzeFoodFromImage: async () => qwenResult };
      throw new Error(`unexpected require ${request}`);
    },
  });
  page.data = { ...page.data, imagePath: 'wxfile://meal.jpg', remaining: 20 };
  page.setData = patch => Object.assign(page.data, patch);

  await page.analyze();
  assert.equal(page.data.result.mealId, 42);
  assert.equal(page.data.result.items[0].name, '米饭');
  assert.equal(page.data.remaining, 19);
  page.viewReport();
  assert.equal(opened, '/pages/report/report?id=42');
});
