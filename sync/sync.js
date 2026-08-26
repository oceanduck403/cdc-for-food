/**
 * 疾控知识库 RSS 同步脚本
 * 
 * 功能：从多个权威公众号 RSS 源抓取文章，
 *       转换成小程序知识库需要的 JSON 格式，
 *       输出到 data/knowledge.json
 * 
 * 使用方式：
 *   node sync.js           # 本地运行
 *   GitHub Actions 自动运行 # 每天定时
 */

import Parser from 'rss-parser';
import { writeFileSync, mkdirSync, existsSync } from 'fs';
import { SOURCES, TAG_COLORS } from './sources.js';

// 初始化 RSS 解析器
const parser = new Parser({
  timeout: 10000,
  headers: {
    'User-Agent': 'Mozilla/5.0 (compatible; CDC-Knowledge-Sync/1.0)'
  }
});

// 工具函数：清理 HTML 标签，保留纯文本
function stripHtml(html) {
  if (!html) return '';
  return html
    .replace(/<[^>]*>/g, '')
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 200); // 限制摘要长度
}

// 工具函数：从 URL 提取文章 ID
function extractArticleId(url) {
  if (!url) return '';
  // 尝试匹配 jintiankansha.com 的文章 ID
  const match = url.match(/\/t\/([A-Za-z0-9]+)/);
  return match ? match[1] : url.slice(-20);
}

// 工具函数：格式化日期
function formatDate(date) {
  const d = new Date(date);
  return d.toISOString().split('T')[0]; // YYYY-MM-DD
}

// 工具函数：生成唯一 ID
function generateId(sourceId, title, pubDate) {
  const str = `${sourceId}-${title}-${pubDate}`;
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash;
  }
  return `art-${Math.abs(hash).toString(16).padStart(8, '0')}`;
}

// 工具函数：分类文章
function classifyArticle(title, content) {
  const text = (title + content).toLowerCase();
  
  if (text.includes('疫苗') || text.includes('接种') || text.includes('HPV') || text.includes('流感针')) {
    return 'vaccine';
  }
  if (text.includes('营养') || text.includes('膳食') || text.includes('饮食') || text.includes('食物') || text.includes('蔬菜') || text.includes('水果')) {
    return 'guide';
  }
  if (text.includes('毒蘑菇') || text.includes('野生菌') || text.includes('蘑菇') || text.includes('菌类')) {
    return 'mushroom';
  }
  if (text.includes('食物中毒') || text.includes('食源性疾病') || text.includes('沙门氏菌') || text.includes('诺如')) {
    return 'disease';
  }
  if (text.includes('安全') || text.includes('检测') || text.includes('农药') || text.includes('添加剂')) {
    return 'safety';
  }
  
  return 'disease'; // 默认归类为疾病
}

// 主函数：抓取单个 RSS 源
async function fetchSource(source) {
  console.log(`📡 正在抓取: ${source.name}...`);
  
  try {
    const feed = await parser.parseURL(source.rss);
    const items = (feed.items || []).slice(0, 20); // 最多取 20 篇
    
    console.log(`   ✅ 获取 ${items.length} 篇文章`);
    
    return items.map(item => {
      const articleCategory = classifyArticle(
        item.title || '',
        item.contentSnippet || ''
      );
      
      return {
        id: generateId(source.id, item.title, item.pubDate),
        title: stripHtml(item.title || '无标题'),
        summary: stripHtml(item.contentSnippet || item.content || ''),
        source: source.name,
        sourceUrl: item.link || '',
        updatedAt: formatDate(item.pubDate || item.isoDate || new Date()),
        category: articleCategory,
        tagColor: TAG_COLORS[articleCategory]?.bg || '#E8F5F0',
        // 保留原始链接用于跳转
        originalUrl: item.link || ''
      };
    });
  } catch (error) {
    console.error(`   ❌ 抓取失败: ${error.message}`);
    return [];
  }
}

// 主函数：合并并排序文章
function mergeArticles(allArticles) {
  // 按更新时间倒序排列
  allArticles.sort((a, b) => {
    const dateA = new Date(a.updatedAt);
    const dateB = new Date(b.updatedAt);
    return dateB - dateA;
  });
  
  return allArticles;
}

// 主函数：生成分类索引
function generateCategoryIndex(articles) {
  const categories = {};
  
  for (const article of articles) {
    const cat = article.category;
    if (!categories[cat]) {
      categories[cat] = { items: [] };
    }
    categories[cat].items.push(article);
  }
  
  return categories;
}

// 主函数：保存结果
function saveResults(articles, categories) {
  const outputDir = 'data';
  if (!existsSync(outputDir)) {
    mkdirSync(outputDir, { recursive: true });
  }
  
  // 保存完整列表
  const allData = {
    version: new Date().toISOString(),
    total: articles.length,
    items: articles
  };
  
  writeFileSync(
    `${outputDir}/knowledge.json`,
    JSON.stringify(allData, null, 2),
    'utf8'
  );
  console.log(`\n📝 已保存: ${outputDir}/knowledge.json (${articles.length} 篇文章)`);
  
  // 保存分类索引
  const indexData = {
    version: new Date().toISOString(),
    categories: Object.keys(categories),
    ...categories
  };
  
  writeFileSync(
    `${outputDir}/knowledge-index.json`,
    JSON.stringify(indexData, null, 2),
    'utf8'
  );
  console.log(`📝 已保存: ${outputDir}/knowledge-index.json`);
}

// 主函数
async function main() {
  console.log('🔄 疾控知识库 RSS 同步开始...\n');
  console.log(`⏰ 时间: ${new Date().toLocaleString('zh-CN')}`);
  console.log(`📚 来源数量: ${SOURCES.length}\n`);
  
  const allArticles = [];
  
  // 依次抓取每个源
  for (const source of SOURCES) {
    const articles = await fetchSource(source);
    allArticles.push(...articles);
    // 避免请求过快
    await new Promise(r => setTimeout(r, 1000));
  }
  
  // 合并并排序
  const merged = mergeArticles(allArticles);
  
  // 生成分类索引
  const categories = generateCategoryIndex(merged);
  
  // 保存结果
  saveResults(merged, categories);
  
  console.log('\n✨ 同步完成！');
}

// 运行
main().catch(console.error);
