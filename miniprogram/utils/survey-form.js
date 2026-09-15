// 将模板和展示状态统一放在 JS 中处理，WXML 只渲染当前页。
function normalizeQuestions(value) {
  let questions = value;
  if (typeof questions === 'string') questions = JSON.parse(questions);
  if (!Array.isArray(questions)) throw new Error('问卷题目格式不正确');
  const normalized = questions.map((q, index) => {
    if (!q || !q.id || !q.title) throw new Error('问卷题目不完整');
    const step = Number(q.step);
    return { ...q, number: index + 1, step: Number.isInteger(step) && step >= 0 ? step : 0 };
  });
  const steps = [...new Set(normalized.map(q => q.step))].sort((a, b) => a - b);
  return normalized.map(q => ({ ...q, step: steps.indexOf(q.step) }));
}

function currentQuestions(questions, step, answers) {
  return questions.filter(q => q.step === step).map(q => ({
    ...q,
    choices: (q.options || []).map(value => ({
      value,
      selected: Array.isArray(answers[q.id]) ? answers[q.id].includes(value) : answers[q.id] === value,
    })),
  }));
}

module.exports = { normalizeQuestions, currentQuestions };
