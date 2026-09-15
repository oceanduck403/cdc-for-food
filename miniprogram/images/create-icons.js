// miniprogram/images/create-icons.js
// 运行此脚本生成 tabBar 图标
// 在微信开发者工具的「编译」控制台执行，或复制输出到文件

const fs = wx.getFileSystemManager();

// 图标尺寸
const SIZE = 81;

// 基础 SVG 模板
function createSvg(color, pathD, bgColor = null) {
  const bg = bgColor ? `<circle cx="40.5" cy="40.5" r="40" fill="${bgColor}"/>` : '';
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${SIZE}" height="${SIZE}" viewBox="0 0 ${SIZE} ${SIZE}">
  ${bg}
  <path d="${pathD}" fill="${color}" transform="translate(16,16) scale(1.5)"/>
</svg>`;
}

// 调查评估图标 - 问卷/表格
const surveyPath = 'M3,3h6v2h-4v2h3v2h-3v2h4v2h-6v-10zm10,0h6v2h-4v2h3v2h-3v2h4v2h-6v-10zm10,4h2v6h-2v-6zm-10,0h2v6h-2v-6z';

// 打卡指导图标 - 日历/勾选
const checkinPath = 'M19,3h-1v-1h-2v1h-1v1h-1v2h1v-1h2v1h1v-1h1v-1zm1,8h-14v8h14v-8zm-7,4l-4-4 1.41-1.41 2.59,2.58 6.59-6.59 1.41,1.42-8,8z';

// 咨询图标 - 消息气泡
const consultPath = 'M20,2h-16c-1.1,0 -1.99,0.9 -1.99,2l-1.99,15.09c0,0.55 0.45,1 1,1h14c0.55,0 1,-0.45 1,-1v-14.1c0,-1.1 -0.9,-1.99 -2,-1.99zm0,14h-12.59l-2.3,-2.3 0.71,-0.71 1.8,1.79 4.18,-4.18 0.71,0.71 -4.89,4.89 0.1,0.1v0.1z';

// 科普图标 - 书本
const sciencePath = 'M18,2h-12c-1.1,0 -2,0.9 -2,2v16c0,1.1 0.9,2 2,2h12c1.1,0 2,-0.9 2,-2v-16c0,-1.1 -0.9,-2 -2,-2zm-12,2h12v16h-12v-16zm2,-2v20h12v-20h-12zm2,4h8v2h-8v-2zm0,4h8v2h-8v-2zm0,4h5v2h-5v-2z';

// 我的图标 - 人物
const minePath = 'M12,12c2.21,0 4,-1.79 4,-4s-1.79,-4 -4,-4 -4,1.79 -4,4 1.79,4 4,4zm0,2c-2.67,0 -8,1.34 -8,4v2h16v-2c0,-2.66 -5.33,-4 -8,-4z';

// 创建并保存图标的函数（需在 Node.js 环境运行）
function generateIcons() {
  const icons = [
    { name: 'survey', path: surveyPath, color: '#0F8A65', bg: '#E8F5F0' },
    { name: 'checkin', path: checkinPath, color: '#F59E0B', bg: '#FEF3C7' },
    { name: 'consult', path: consultPath, color: '#EF4444', bg: '#FEE2E2' },
    { name: 'science', path: sciencePath, color: '#3B82F6', bg: '#DBEAFE' },
    { name: 'mine', path: minePath, color: '#8B5CF6', bg: '#EDE9FE' },
  ];

  icons.forEach(icon => {
    const svg = createSvg(icon.color, icon.path, icon.bg);
    const filename = `icon_${icon.name}.svg`;
    console.log(`\n=== ${filename} ===`);
    console.log(svg);
  });
}

module.exports = { generateIcons };
