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

function hasAnswer(value) {
  return value !== undefined && value !== null &&
    (typeof value !== 'string' || value.trim() !== '') &&
    (!Array.isArray(value) || value.length > 0);
}

// 跳题条件只依赖当前仍可见的父题，避免隐藏题残留答案再次触发子题。
function visibleQuestions(questions, answers = {}) {
  const byId = new Map(questions.map(q => [q.id, q]));
  const visible = (question, visiting = new Set()) => {
    const condition = question.showWhen;
    if (!condition) return true;
    if (visiting.has(question.id)) return false;
    const parent = byId.get(condition.questionId);
    const value = answers[condition.questionId];
    if (!parent || !hasAnswer(value)) return false;
    const next = new Set(visiting);
    next.add(question.id);
    if (!visible(parent, next)) return false;
    const operators = ['equals', 'notEquals', 'includes'].filter(key => Object.prototype.hasOwnProperty.call(condition, key));
    if (!operators.length) return false;
    return operators.every(key => key === 'equals' ? value === condition.equals :
      key === 'notEquals' ? value !== condition.notEquals :
        Array.isArray(value) && value.includes(condition.includes));
  };
  return questions.filter(q => visible(q));
}

function visibleAnswers(questions, answers = {}) {
  const result = {};
  for (const question of visibleQuestions(questions, answers)) {
    if (Object.prototype.hasOwnProperty.call(answers, question.id)) result[question.id] = answers[question.id];
  }
  return result;
}

function currentQuestions(questions, step, answers = {}) {
  let lastSection = '';
  return visibleQuestions(questions, answers).filter(q => q.step === step).map(q => {
    const sectionHeading = q.section && q.section !== lastSection ? q.section : '';
    if (q.section) lastSection = q.section;
    return {
      ...q,
      sectionHeading,
      answerValue: answers[q.id] === undefined || answers[q.id] === null ? '' : answers[q.id],
      choices: (q.options || []).map(value => ({
        value,
        selected: Array.isArray(answers[q.id]) ? answers[q.id].includes(value) : answers[q.id] === value,
      })),
    };
  });
}

module.exports = { normalizeQuestions, currentQuestions, visibleQuestions, visibleAnswers };
