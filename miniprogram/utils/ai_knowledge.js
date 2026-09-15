// utils/ai_knowledge.js
// 科普知识 AI 问答
const { chat } = require('./qwen_chat.js');

const KNOWLEDGE_SYSTEM_PROMPT = `你是一位专业的营养与食品安全科普专家，擅长用通俗易懂的语言解答健康相关问题。

你的职责：
1. 回答用户的健康相关问题（营养、食品安全、疾病预防等）
2. 提供科学、准确的信息
3. 避免过于专业的术语，多用简单的例子
4. 如问题超出科普范围，明确告知

回答格式：
- 直接回答用户问题
- 给出实用建议
- 适当补充相关知识

⚠️ 重要提醒：你的回答仅供参考，不作为诊疗依据。如有不适请及时就医。`;

/**
 * AI 知识问答
 * @param {string} question - 用户问题
 * @returns {Promise<string>}
 */
async function askKnowledge(question) {
  return chat(question, 'health_consult');
}

/**
 * 生成知识摘要
 * @param {string} topic - 主题
 * @returns {Promise<string>}
 */
async function generateSummary(topic) {
  const prompt = `请用简洁的语言总结"${topic}"这个健康话题的核心要点，300字以内。要求通俗易懂，适合普通用户阅读。`;
  return chat(prompt, 'health_consult');
}

/**
 * 智能搜索（在搜索结果中用 AI 排序/补全）
 * @param {string} keyword - 关键词
 * @param {Array} results - 搜索结果
 * @returns {Promise<Array>} 排序后的结果
 */
async function smartSearch(keyword, results) {
  if (!keyword || results.length === 0) return results;

  const prompt = `用户搜索关键词："${keyword}"

请从以下文章标题中选出最相关的 5 篇（按相关度排序），只返回排序后的编号列表（如：3,1,5,2,4）：

${results.map((item, i) => `${i + 1}. ${item.title}`).join('\n')}`;

  try {
    const reply = await chat(prompt, 'health_consult');
    // 解析返回的编号
    const numbers = reply.match(/\d+/g);
    if (numbers && numbers.length > 0) {
      const sortedResults = numbers.slice(0, 5).map(n => {
        const idx = parseInt(n) - 1;
        return results[idx];
      }).filter(Boolean);
      return sortedResults.length > 0 ? sortedResults : results.slice(0, 5);
    }
    return results.slice(0, 5);
  } catch (err) {
    return results.slice(0, 5);
  }
}

module.exports = {
  askKnowledge,
  generateSummary,
  smartSearch,
  KNOWLEDGE_SYSTEM_PROMPT
};
