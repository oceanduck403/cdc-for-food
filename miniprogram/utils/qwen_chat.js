// AI 文本能力统一经自有后端调用，第三方服务密钥不会进入小程序包。
const { request } = require('./request.js');

function chat(userMessage, mode = 'health_consult') {
  return request({
    url: '/ai/chat',
    method: 'POST',
    data: { message: String(userMessage || '').trim(), mode, history: [] },
    showLoading: false,
    silent: true
  }).then(data => data.reply);
}

function chatWithHistory(userMessage, history = [], mode = 'health_consult') {
  const safeHistory = (Array.isArray(history) ? history : [])
    .filter(item => item && (item.role === 'user' || item.role === 'assistant') && item.content)
    .slice(-12)
    .map(item => ({ role: item.role, content: String(item.content).slice(0, 2000) }));
  const message = String(userMessage || '').trim();
  return request({
    url: '/ai/chat',
    method: 'POST',
    data: { message, mode, history: safeHistory },
    showLoading: false,
    silent: true
  }).then(data => ({
    reply: data.reply,
    history: [...safeHistory, { role: 'user', content: message }, { role: 'assistant', content: data.reply }]
  }));
}

function analyzeSurvey(surveyType, answers) {
  return request({
    url: '/ai/survey-analysis',
    method: 'POST',
    data: { surveyType, answers: answers || {} },
    showLoading: false,
    silent: true
  }).then(data => ({
    reply: data.reply,
    surveyType: data.surveyType || surveyType,
    timestamp: Date.now(),
    generatedByAi: true
  }));
}

function generateDailySuggestions(todayData, userProfile) {
  return request({
    url: '/ai/daily-suggestion',
    method: 'POST',
    data: { todayData: todayData || {}, userProfile: userProfile || {} },
    showLoading: false,
    silent: true
  }).then(data => data.reply);
}

module.exports = { chat, chatWithHistory, analyzeSurvey, generateDailySuggestions };
