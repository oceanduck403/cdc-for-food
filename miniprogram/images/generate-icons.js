// generate-icons.js - 生成 tabBar 图标
// 运行: node generate-icons.js
// 需要安装 canvas: npm install canvas

const fs = require('fs');
const path = require('path');

const outDir = __dirname;

const icons = [
  { name: 'survey', label: '调查评估', color: '#0F8A65', bg: '#E8F5F0' },
  { name: 'checkin', label: '打卡指导', color: '#F59E0B', bg: '#FEF3C7' },
  { name: 'consult', label: '免费咨询', color: '#EF4444', bg: '#FEE2E2' },
  { name: 'science', label: '科普互动', color: '#3B82F6', bg: '#DBEAFE' },
  { name: 'mine', label: '我的', color: '#8B5CF6', bg: '#EDE9FE' }
];

async function generateIcons() {
  let canvas, ctx;

  try {
    const { createCanvas } = require('canvas');

    for (const icon of icons) {
      // 创建普通状态图标
      canvas = createCanvas(81, 81);
      ctx = canvas.getContext('2d');
      drawIcon(ctx, icon, false);
      fs.writeFileSync(path.join(outDir, `${icon.name}.png`), canvas.toBuffer('image/png'));

      // 创建选中状态图标
      canvas = createCanvas(81, 81);
      ctx = canvas.getContext('2d');
      drawIcon(ctx, icon, true);
      fs.writeFileSync(path.join(outDir, `${icon.name}_active.png`), canvas.toBuffer('image/png'));

      console.log(`Created: ${icon.name}.png and ${icon.name}_active.png`);
    }
    console.log('\nAll icons generated successfully!');
  } catch (err) {
    console.log('Canvas not available, generating SVG files instead...');
    generateSVGs();
  }
}

function drawIcon(ctx, icon, active) {
  const { color, bg } = icon;

  // 背景圆
  ctx.beginPath();
  ctx.arc(40.5, 40.5, 40, 0, Math.PI * 2);
  ctx.fillStyle = active ? darken(bg, 0.1) : bg;
  ctx.fill();

  // 绘制图标
  ctx.fillStyle = color;
  ctx.strokeStyle = color;
  ctx.lineWidth = 3;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';

  switch (icon.name) {
    case 'survey':
      // 问卷表格
      ctx.beginPath();
      ctx.roundRect(22, 20, 36, 40, 4);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(28, 32); ctx.lineTo(52, 32);
      ctx.moveTo(28, 40); ctx.lineTo(48, 40);
      ctx.moveTo(28, 48); ctx.lineTo(44, 48);
      ctx.stroke();
      break;

    case 'checkin':
      // 日历勾选
      ctx.beginPath();
      ctx.arc(40, 40, 18, 0, Math.PI * 2);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(30, 40); ctx.lineTo(38, 48); ctx.lineTo(52, 32);
      ctx.stroke();
      break;

    case 'consult':
      // 消息气泡
      ctx.beginPath();
      ctx.ellipse(40, 36, 22, 18, 0, 0, Math.PI * 2);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(34, 52); ctx.lineTo(34, 58); ctx.lineTo(42, 52);
      ctx.closePath();
      ctx.fill();
      // 眼睛和嘴巴
      ctx.beginPath();
      ctx.arc(34, 34, 3, 0, Math.PI * 2);
      ctx.arc(46, 34, 3, 0, Math.PI * 2);
      ctx.fill();
      ctx.beginPath();
      ctx.arc(40, 44, 6, 0, Math.PI);
      ctx.stroke();
      break;

    case 'science':
      // 书本
      ctx.beginPath();
      ctx.roundRect(24, 20, 32, 42, 2);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(40, 20); ctx.lineTo(40, 62);
      ctx.stroke();
      ctx.font = '10px Arial';
      ctx.fillText('A', 28, 30);
      ctx.fillText('B', 46, 30);
      break;

    case 'mine':
      // 人物
      ctx.beginPath();
      ctx.arc(40, 30, 12, 0, Math.PI * 2);
      ctx.fill();
      ctx.beginPath();
      ctx.ellipse(40, 56, 16, 12, 0, 0, Math.PI * 2);
      ctx.fill();
      break;
  }
}

function darken(color, amount) {
  const hex = color.replace('#', '');
  const r = Math.max(0, parseInt(hex.substr(0, 2), 16) * (1 - amount));
  const g = Math.max(0, parseInt(hex.substr(2, 2), 16) * (1 - amount));
  const b = Math.max(0, parseInt(hex.substr(4, 2), 16) * (1 - amount));
  return `rgb(${Math.round(r)},${Math.round(g)},${Math.round(b)})`;
}

function generateSVGs() {
  for (const icon of icons) {
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="81" height="81">
  <circle cx="40.5" cy="40.5" r="40" fill="${icon.bg}"/>
  <text x="40.5" y="55" text-anchor="middle" font-size="40">${getEmoji(icon.name)}</text>
</svg>`;
    fs.writeFileSync(path.join(outDir, `${icon.name}.svg`), svg);
    console.log(`Created: ${icon.name}.svg`);
  }
  console.log('\nSVG files created. Open in browser and screenshot to create PNGs.');
}

function getEmoji(name) {
  const map = { survey: '📋', checkin: '✅', consult: '💬', science: '📚', mine: '👤' };
  return map[name] || '📱';
}

generateIcons();
