// pages/survey-form/survey-form.js
// 调查问卷表单页面 - 支持后端模板 + 提交到后端
const surveyApi = require('../../utils/survey.js');
const { analyzeSurvey } = require('../../utils/qwen_chat.js');
const { normalizeQuestions, currentQuestions } = require('../../utils/survey-form.js');

// ── 本地问卷题库（备用）────────────────────────────────────────
const LOCAL_QUESTIONS = {
  diet: [
    { id: 'q1', type: 'radio', title: '您的年龄范围？', options: ['18-30岁', '31-45岁', '46-60岁', '60岁以上'] },
    { id: 'q2', type: 'radio', title: '您的性别？', options: ['男', '女', '不方便透露'] },
    { id: 'q3', type: 'checkbox', title: '您通常一天吃几顿饭？', options: ['1顿', '2顿', '3顿', '4顿以上', '不规律'] },
    { id: 'q4', type: 'radio', title: '您经常吃早餐吗？', options: ['每天吃', '偶尔吃', '很少吃', '从不吃'] },
    { id: 'q5', type: 'checkbox', title: '您经常吃以下哪些食物？（多选）', options: ['蔬菜水果', '肉类', '海鲜', '油炸食品', '腌制食品', '甜食'] },
    { id: 'q6', type: 'input', title: '您每天大概喝多少水？（单位：毫升）', placeholder: '请输入' },
    { id: 'q7', type: 'radio', title: '您有食物过敏史吗？', options: ['没有', '有（请说明）'] },
    { id: 'q8', type: 'input', title: '如有过敏，请说明过敏源', placeholder: '如：海鲜、芒果等' },
    { id: 'q9', type: 'radio', title: '您平时口味偏好？', options: ['清淡', '适中', '偏咸', '偏辣', '偏甜'] },
    { id: 'q10', type: 'radio', title: '您有慢性病史吗？', options: ['没有', '有糖尿病', '有高血压', '有高血脂', '有痛风'] },
  ],
  lifestyle: [
    { id: 'l1', type: 'radio', title: '您每周运动几次？', options: ['从不', '1-2次', '3-4次', '5次以上'] },
    { id: 'l2', type: 'input', title: '您每次运动多长时间？（单位：分钟）', placeholder: '请输入' },
    { id: 'l3', type: 'checkbox', title: '您通常做什么运动？（多选）', options: ['散步', '跑步', '游泳', '骑车', '打球', '瑜伽/太极', '其他'] },
    { id: 'l4', type: 'radio', title: '您每天睡眠大约多少小时？', options: ['<6小时', '6-7小时', '7-8小时', '>8小时'] },
    { id: 'l5', type: 'radio', title: '您的睡眠质量如何？', options: ['很好', '较好', '一般', '较差', '很差'] },
    { id: 'l6', type: 'radio', title: '您平时工作压力大吗？', options: ['很大', '较大', '一般', '较小', '无压力'] },
    { id: 'l7', type: 'radio', title: '您有吸烟习惯吗？', options: ['从不吸烟', '偶尔吸烟', '经常吸烟', '已戒烟'] },
    { id: 'l8', type: 'radio', title: '您有饮酒习惯吗？', options: ['从不饮酒', '偶尔小酌', '经常饮酒', '已戒酒'] },
  ],
  health: [
    { id: 'h1', type: 'radio', title: '您目前健康状况如何？', options: ['很好', '较好', '一般', '较差', '很差'] },
    { id: 'h2', type: 'checkbox', title: '您有以下哪些症状？（多选）', options: ['无明显症状', '经常疲劳', '睡眠不好', '食欲不振', '消化不良', '体重异常'] },
    { id: 'h3', type: 'radio', title: '您有慢性病吗？', options: ['没有', '有1种', '有2种', '有3种以上'] },
    { id: 'h4', type: 'input', title: '如有，请说明病名', placeholder: '如：高血压、糖尿病等' },
    { id: 'h5', type: 'radio', title: '您有长期服药吗？', options: ['没有', '有（请说明）'] },
    { id: 'h6', type: 'input', title: '如有，请说明药物名称', placeholder: '请输入药物名称' },
    { id: 'h7', type: 'radio', title: '您有家族遗传病史吗？', options: ['没有', '有（请说明）'] },
    { id: 'h8', type: 'input', title: '如有，请说明', placeholder: '如：糖尿病、高血压等' },
  ],
  food_safety: [
    { id: 'f1', type: 'radio', title: '您了解食品安全知识吗？', options: ['很了解', '了解一些', '不太了解', '完全不了解'] },
    { id: 'f2', type: 'checkbox', title: '您关注以下哪些食品安全问题？（多选）', options: ['农药残留', '添加剂超标', '重金属污染', '微生物污染', '假冒伪劣', '过期食品'] },
    { id: 'f3', type: 'radio', title: '您外出就餐会看餐厅卫生等级吗？', options: ['每次都看', '经常看', '偶尔看', '从不看'] },
    { id: 'f4', type: 'radio', title: '您会吃过期食品吗？', options: ['从不会', '偶尔会', '看情况', '经常会'] },
    { id: 'f5', type: 'radio', title: '您知道如何正确保存食物吗？', options: ['非常清楚', '知道一些', '不太清楚', '完全不知道'] },
    { id: 'f6', type: 'radio', title: '您吃过野生蘑菇吗？', options: ['从未吃过', '偶尔吃', '经常吃'] },
    { id: 'f7', type: 'radio', title: '您知道毒蘑菇的危害吗？', options: ['非常了解', '了解一些', '不太了解', '完全不了解'] },
  ],
};

Page({
  data: {
    surveyType: '',
    templateId: null,       // 后端模板 ID（非空=后端模板）
    surveyTitle: '',
    mode: 'edit',           // edit | view | analyze
    currentStep: 0,
    totalSteps: 0,
    currentQuestions: [],
    loading: false,
    loadError: '',
    submitting: false,
    answers: {},
    questions: [],          // 动态题目数组（后端或本地）
    submitted: false,
    draftSaved: false,
    analyzing: false,
    analysisResult: null,
    isRemote: false,       // 是否后端模板
    responseId: null,       // 历史提交 ID
  },

  onLoad(options) {
    // ── 查看历史记录 ──
    if (options.id) {
      this.setData({ mode: 'view', responseId: options.id });
      return this.loadHistory(options.id);
    }

    // ── 新填写 ──
    const surveyTitle = decodeURIComponent(options.title || '问卷调查');
    this.setData({ surveyType: options.type || '', surveyTitle });

    if (options.templateId !== undefined) {
      // 后端模板
      return this.loadRemoteTemplate(Number(options.templateId));
    } else {
      // 本地问卷
      this.loadLocalQuestions(options.type);
    }
  },

  // ── 加载后端模板 ──
  async loadRemoteTemplate(templateId) {
    this.setData({ loading: true, loadError: '', templateId, isRemote: true });
    wx.showLoading({ title: '加载中...', mask: true });
    try {
      if (!Number.isInteger(templateId) || templateId <= 0) {
        throw new Error('问卷链接无效，请返回列表重新选择');
      }
      const tpl = await surveyApi.getTemplate(templateId);
      const qs = normalizeQuestions(tpl.questions);
      if (!qs.length) throw new Error('该问卷暂无题目，请联系管理员');
      this.setData({
        templateId,
        isRemote: true,
        surveyType: tpl.type || this.data.surveyType,
        questions: qs,
        surveyTitle: tpl.name || tpl.title || '问卷',
        totalSteps: Math.max(...qs.map(q => q.step)) + 1,
        currentStep: 0,
      });
      this.restoreDraft();
      this.updateCurrentQuestions();
    } catch (err) {
      this.setData({ loadError: err.message || '加载问卷失败，请重试', questions: [], currentQuestions: [], totalSteps: 0 });
    } finally {
      this.setData({ loading: false });
      wx.hideLoading();
    }
  },

  // ── 加载本地题库 ──
  loadLocalQuestions(type) {
    const qs = normalizeQuestions(LOCAL_QUESTIONS[type] || []);
    const maxStep = qs.length > 0 ? Math.max(...qs.map(q => q.step)) + 1 : 0;
    this.setData({ questions: qs, isRemote: false, totalSteps: maxStep, loadError: qs.length ? '' : '问卷不存在，请返回列表重新选择' });
    this.updateCurrentQuestions();
  },

  // ── 加载历史记录 ──
  async loadHistory(id) {
    this.setData({ loading: true, loadError: '' });
    wx.showLoading({ title: '加载中...', mask: true });
    try {
      const local = (wx.getStorageSync('survey_history') || []).find(r => String(r.id) === String(id));
      const r = local ? {
        template_type: local.type, template_name: local.title,
        answers: local.answers, questions: local.questions || LOCAL_QUESTIONS[local.type],
      } : await surveyApi.getMyResponseDetail(id);
      // 获取关联模板的题目
      let qs = [];
      if (r.questions && r.questions.length > 0) {
        qs = r.questions;
      } else if (r.template_type && LOCAL_QUESTIONS[r.template_type]) {
        qs = LOCAL_QUESTIONS[r.template_type];
      }
      qs = normalizeQuestions(qs);
      if (!qs.length) throw new Error('该记录的问卷题目不存在');
      const maxStep = Math.max(...qs.map(q => q.step)) + 1;
      this.setData({
        surveyType: r.template_type || '',
        surveyTitle: r.template_name || r.template_type || '问卷',
        questions: qs,
        answers: r.answers || {},
        isRemote: !local,
        totalSteps: maxStep,
        currentStep: 0,
        analysisResult: r.analysis ? { reply: r.analysis } : null,
        mode: r.analysis ? 'analyze' : 'view',
      });
      this.updateCurrentQuestions();
    } catch (err) {
      this.setData({ loadError: err.message || '加载记录失败，请重试' });
    } finally {
      this.setData({ loading: false });
      wx.hideLoading();
    }
  },

  // ── 获取当前步骤题目 ──
  getCurrentQuestions() {
    return currentQuestions(this.data.questions, this.data.currentStep, this.data.answers);
  },

  updateCurrentQuestions() {
    this.setData({ currentQuestions: this.getCurrentQuestions() });
  },

  retryLoad() {
    if (this.data.responseId) return this.loadHistory(this.data.responseId);
    if (this.data.isRemote) return this.loadRemoteTemplate(this.data.templateId);
    this.loadLocalQuestions(this.data.surveyType);
  },

  // ── 单选 ──
  draftKey() {
    const profile = wx.getStorageSync('profile') || {};
    return profile.id && this.data.templateId ? `survey_draft_${profile.id}_${this.data.templateId}` : '';
  },
  saveDraft() {
    const key = this.draftKey();
    if (!key || this.data.mode !== 'edit' || this.data.submitted || this.data.loadError || !this.data.questions.length) return;
    try {
      wx.setStorageSync(key, { answers: this.data.answers, currentStep: this.data.currentStep, schema: JSON.stringify(this.data.questions) });
      this.setData({ draftSaved: true });
    } catch (_) { this.setData({ draftSaved: false }); }
  },
  restoreDraft() {
    const key = this.draftKey();
    if (!key || this.data.mode !== 'edit') return;
    const draft = wx.getStorageSync(key);
    if (draft && draft.schema === JSON.stringify(this.data.questions)) {
      this.setData({ answers: draft.answers || {}, currentStep: Math.min(draft.currentStep || 0, this.data.totalSteps - 1), draftSaved: true });
    }
  },
  onHide() { this.saveDraft(); },
  onUnload() { this.saveDraft(); },

  onRadioChange(e) {
    if (this.data.mode === 'view' || this.data.submitted) return;
    const { id, value } = e.currentTarget.dataset;
    this.setData({ [`answers.${id}`]: value });
    this.saveDraft();
    this.updateCurrentQuestions();
  },

  // ── 多选 ──
  onCheckboxChange(e) {
    if (this.data.mode === 'view' || this.data.submitted) return;
    const { id } = e.currentTarget.dataset;
    this.setData({ [`answers.${id}`]: e.detail.value });
    this.saveDraft();
    this.updateCurrentQuestions();
  },

  // ── 输入 ──
  onInputChange(e) {
    if (this.data.mode === 'view' || this.data.submitted) return;
    const { id } = e.currentTarget.dataset;
    this.setData({ [`answers.${id}`]: e.detail.value });
    this.saveDraft();
  },

  // ── 下一步 ──
  clearDate(e) {
    this.onInputChange({ currentTarget: e.currentTarget, detail: { value: '' } });
  },

  nextStep() {
    if (this.data.loading || this.data.loadError || this.data.submitting) return;
    const { currentStep, totalSteps } = this.data;
    if (currentStep < totalSteps - 1) {
      this.setData({ currentStep: currentStep + 1 });
      this.updateCurrentQuestions();
      wx.pageScrollTo({ scrollTop: 0, duration: 0 });
    }
  },

  // ── 上一步 ──
  prevStep() {
    const { currentStep } = this.data;
    if (currentStep > 0) {
      this.setData({ currentStep: currentStep - 1 });
      this.updateCurrentQuestions();
      wx.pageScrollTo({ scrollTop: 0, duration: 0 });
    }
  },

  // ── 提交 ──
  submitSurvey() {
    if (this.data.mode === 'view' || this.data.submitted || this.data.submitting || this.data.loading || this.data.loadError || !this.data.questions.length) return;
    const { answers, questions } = this.data;
    const unanswered = questions.filter(q => {
      const ans = answers[q.id];
      return ans === undefined || ans === null || (typeof ans === 'string' && !ans.trim()) || (Array.isArray(ans) && ans.length === 0);
    });

    if (unanswered.length > 0) {
      wx.showModal({
        title: '提示',
        content: `还有 ${unanswered.length} 道题未填写，是否确认提交？`,
        success: res => { if (res.confirm) this.doSubmit(); },
      });
    } else {
      this.doSubmit();
    }
  },

  async doSubmit() {
    if (this.data.submitting || this.data.submitted || this.data.mode === 'view' || this.data.loadError || !this.data.questions.length) return;
    this.setData({ submitting: true });
    const { templateId, isRemote, answers, surveyType } = this.data;
    wx.showLoading({ title: '提交中...', mask: true });

    try {
      if (isRemote && templateId) {
        // 提交到后端
        const profile = wx.getStorageSync('profile') || {};
        const result = await surveyApi.submitResponse({
          template_id: templateId,
          answers,
          total_score: 0,
          analysis: '',
          user_name: surveyType === 'weight_visit_registration' ? (answers.name || '') : (profile.real_name || profile.nickname || ''),
          user_phone: surveyType === 'weight_visit_registration' ? (answers.phone || '') : (profile.phone || ''),
          submitted_at: new Date().toLocaleString('zh-CN'),
        });
        this.setData({ responseId: result.id });
      } else {
        // 降级到本地存储
        const history = wx.getStorageSync('survey_history') || [];
        history.unshift({
          id: Date.now(),
          type: surveyType,
          title: this.data.surveyTitle,
          date: new Date().toLocaleDateString(),
          answers,
          questions: this.data.questions,
        });
        wx.setStorageSync('survey_history', history);
      }

      this.setData({ submitted: true });
      const draftKey = this.draftKey();
      if (draftKey) wx.removeStorageSync(draftKey);
      wx.hideLoading();
      wx.showToast({ title: '提交成功！', icon: 'success' });

      // 登记表不作健康评分或 AI 分析。
      if (surveyType === 'weight_visit_registration') {
        this.setData({ mode: 'view' });
        wx.showModal({ title: '登记成功', content: '就诊信息已保存，可在填写记录中查看。', showCancel: false, success: () => wx.navigateBack() });
        return;
      }

      setTimeout(() => {
        wx.showModal({
          title: '问卷已提交',
          content: '是否需要 AI 智能分析您的问卷结果？',
          confirmText: '立即分析',
          cancelText: '稍后再说',
          success: res => {
            if (res.confirm) this.analyzeResults();
            else wx.navigateBack();
          },
        });
      }, 1500);
    } catch (err) {
      wx.hideLoading();
      wx.showToast({ title: err.message || '提交失败', icon: 'none' });
    } finally {
      this.setData({ submitting: false });
    }
  },

  // ── AI 分析 ──
  async analyzeResults() {
    const { surveyType, answers, surveyTitle } = this.data;
    this.setData({ analyzing: true });
    wx.showLoading({ title: 'AI 分析中...' });

    try {
      const result = await analyzeSurvey(surveyType, answers);
      this.setData({ analyzing: false, analysisResult: result, mode: 'analyze' });
    } catch (err) {
      wx.hideLoading();
      this.setData({ analyzing: false });
      const offline = this._generateOfflineAnalysis(surveyType, answers);
      this.setData({ analysisResult: { reply: offline }, mode: 'analyze' });
    } finally {
      wx.hideLoading();
    }
  },

  _generateOfflineAnalysis(type, answers) {
    const names = { diet: '膳食调查', lifestyle: '生活方式', health: '健康状况', food_safety: '食品安全' };
    const TYPE_NAMES = { weight_clinic_first: '体重管理首诊', weight_clinic_follow: '体重管理复诊' };
    const name = TYPE_NAMES[type] || names[type] || '问卷';
    let score = 50, findings = [], suggestions = [];

    if (type === 'diet') {
      if (answers.q4 === '每天吃') { score += 20; findings.push('✓ 早餐习惯良好'); }
      else if (answers.q4 === '偶尔吃') { score += 10; findings.push('△ 偶尔吃早餐，需改善'); }
      if (answers.q5?.includes?.('蔬菜水果')) { score += 20; findings.push('✓ 摄入蔬菜水果'); }
      if (answers.q5?.includes?.('油炸食品')) { score -= 10; findings.push('油炸食品摄入偏多'); }
      suggestions = ['坚持每天吃早餐', '多吃蔬菜水果，每天至少500g', '控制油盐糖摄入'];
    } else if (type === 'lifestyle') {
      if (answers.l1 === '5次以上') { score += 25; findings.push('✓ 运动习惯良好'); }
      if (answers.l4 === '7-8小时') { score += 25; findings.push('✓ 睡眠时长合适'); }
      suggestions = ['每周至少运动3-5次', '保持7-8小时睡眠', '戒烟限酒'];
    } else if (type === 'health') {
      if (answers.h1 === '很好' || answers.h1 === '较好') { score += 30; findings.push('✓ 自我健康评价良好'); }
      suggestions = ['定期体检，关注身体变化', '如有不适症状，及时就医'];
    } else if (type === 'food_safety') {
      if (answers.f1 === '很了解') { score += 25; findings.push('✓ 食品安全知识丰富'); }
      if (answers.f6 !== '经常吃') { score += 15; findings.push('✓ 野生蘑菇食用谨慎'); }
      suggestions = ['提高食品安全意识', '切勿随意采摘和食用野生蘑菇'];
    } else {
      // 体重管理类问卷
      findings.push('根据您填写的健康信息');
      suggestions = ['坚持健康饮食', '适度运动', '定期复查'];
    }

    score = Math.min(100, Math.max(0, score));
    const level = score >= 80 ? '优秀' : score >= 60 ? '良好' : score >= 40 ? '一般' : '需改善';
    return `${name}分析报告\n\n综合评分：${score}/100（${level}）\n\n【主要发现】\n${findings.map(f => `• ${f}`).join('\n') || '• 数据已记录'}\n\n【改进建议】\n${suggestions.map((s, i) => `${i + 1}. ${s}`).join('\n')}\n\n本分析仅供参考，如有健康问题请咨询专业医生。`;
  },

  goBack() {
    wx.navigateBack();
  },
});
