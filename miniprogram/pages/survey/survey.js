const navigation = require('../../utils/navigation.js');
// pages/survey/survey.js
// 健康评估区 - 问卷列表页面（支持后端动态模板 + 本地旧问卷兼容）
const { request } = require('../../utils/request.js');
const surveyApi = require('../../utils/survey.js');
const { normalizeQuestions } = require('../../utils/survey-form.js');

// 本地兼容旧问卷（备用）
const LOCAL_SURVEYS = [
  {
    id: 'diet', icon: 'leaf', title: '膳食调查问卷',
    desc: '记录您的日常饮食习惯', questionsCount: 10, estimatedTime: '5分钟',
    bgColor: '#EAF3FD', status: '未填写', type: 'local'
  },
  {
    id: 'lifestyle', icon: 'activity', title: '生活方式问卷',
    desc: '运动、睡眠、压力评估', questionsCount: 8, estimatedTime: '8分钟',
    bgColor: '#FEF3C7', status: '未填写', type: 'local'
  },
  {
    id: 'health', icon: 'medicine', title: '健康状况问卷',
    desc: '既往病史、过敏史评估', questionsCount: 8, estimatedTime: '10分钟',
    bgColor: '#FEE2E2', status: '未填写', type: 'local'
  },
  {
    id: 'food_safety', icon: 'shield', title: '食品安全问卷',
    desc: '食品安全知识与行为评估', questionsCount: 7, estimatedTime: '6分钟',
    bgColor: '#EDE9FE', status: '未填写', type: 'local'
  },
].map(item => ({ ...item, url: `/pages/survey-form/survey-form?type=${item.id}&title=${encodeURIComponent(item.title)}` }));

// 后端模板类型颜色映射
const TEMPLATE_COLOR_MAP = {
  'weight_visit_registration': { bgColor: '#DBEAFE', icon: 'calendar' },
  'weight_basic_info':     { bgColor: '#DBEAFE', icon: 'user' },  // 基本信息表
  'weight_clinic_first':   { bgColor: '#DCEBFA', icon: 'survey' },  // 首诊评估表
  'weight_anti_obesity':  { bgColor: '#FEF3C7', icon: 'leaf' },  // 防肥自测表
  'weight_clinic_follow':  { bgColor: '#EDE9FE', icon: 'checkin' },  // 复诊评估表
};

Page({
  data: {
    surveyTypes: [],    // 动态加载的问卷列表（含后端模板+本地兼容）
    historyList: [],
    loading: true,
    loadError: '',
  },

  onShow() {
    // Tab pages are cached. Refresh templates as well as history on every return.
    return this.refresh();
  },

  refresh() {
    return Promise.all([this.loadTemplates(), this.loadSurveyHistory()]);
  },

  // ── 从后端加载问卷模板 ──
  async loadTemplates() {
    if (this._loadingTemplates) return;
    this._loadingTemplates = true;
    this.setData({ loading: true, loadError: '' });
    try {
      const templates = await surveyApi.getTemplates();
      if (!Array.isArray(templates)) {
        throw new Error('问卷数据加载异常，请重新加载');
      }
      if (templates.length === 0) {
        console.warn('后端未返回任何问卷模板');
        this.setData({ surveyTypes: [], loading: false });
        return;
      }
      // 转换为卡片格式
      const remoteTypes = templates.map(t => {
        const qArr = normalizeQuestions(t.questions);
        return {
          id: `remote_${t.id}`,
          templateId: t.id,
          url: `/pages/survey-form/survey-form?templateId=${t.id}&type=${encodeURIComponent(t.type)}&title=${encodeURIComponent(t.name)}`,
          iconPath: '/images/ui/' + ({weight_visit_registration:'calendar',weight_basic_info:'user',weight_clinic_first:'survey',weight_anti_obesity:'leaf',weight_clinic_follow:'checkin'}[t.type] || 'survey') + '.png',
          title: t.name,
          desc: t.description || '点击开始填写',
          questionsCount: qArr.length,
          estimatedTime: `${Math.ceil((qArr.length || 10) * 0.5)}分钟`,
          bgColor: (TEMPLATE_COLOR_MAP[t.type] || { bgColor: '#EAF3FD' }).bgColor,
          status: '未填写',
          type: 'remote',
          templateType: t.type,
          questions: qArr,
        };
      });
      this.setData({
        surveyTypes: remoteTypes,
        loading: false,
      });
      this.updateStatuses();
    } catch (err) {
      console.error('[survey] 加载后端问卷失败:', err);
      this.setData({ surveyTypes: [], loading: false, loadError: err.message || '网络暂时不可用，请检查连接后重试' });
    } finally {
      this._loadingTemplates = false;
    }
  },

  // ── 加载历史记录 ──
  async loadSurveyHistory() {
    try {
      const history = await surveyApi.getMyResponses();
      const historyList = (history || []).map(r => ({
        id: r.id,
        title: r.template_name || r.template_type,
        date: r.submitted_at || r.created_at || '',
        type: 'remote',
        templateId: r.template_id,
        totalScore: r.total_score,
        analysis: r.analysis,
      }));
      this.setData({ historyList });
      this.updateStatuses();
    } catch (err) {
      // 历史记录失败不影响公开问卷列表
      const cache = [];
      this.setData({ historyList: cache });
    }
  },

  onPullDownRefresh() {
    return this.refresh().finally(() => wx.stopPullDownRefresh());
  },
  updateStatuses() {
    const completed = new Set(this.data.historyList.map(r => Number(r.templateId)));
    this.setData({ surveyTypes: this.data.surveyTypes.map(item => ({ ...item, status: completed.has(Number(item.templateId)) ? '已完成' : '未填写' })) });
  },

  // ── 开始填写问卷 ──
  startSurvey(e) {
    const { type } = e.currentTarget.dataset;
    const surveyType = this.data.surveyTypes.find(item => item.id === type);
    if (!surveyType) return;

    if (surveyType.type === 'remote') {
      const templateId = Number(surveyType.templateId);
      if (!Number.isInteger(templateId) || templateId <= 0) {
        wx.showToast({ title: '问卷信息无效，请刷新列表', icon: 'none' });
        return;
      }
      // 后端模板问卷
      navigation.open({
        url: `/pages/survey-form/survey-form?templateId=${templateId}&type=${surveyType.templateType}&title=${encodeURIComponent(surveyType.title)}`,
        fail: err => {
          console.error('[survey] 打开问卷失败:', err);
          wx.showToast({ title: '打开失败，请返回首页后重试', icon: 'none' });
        },
      });
    } else {
      // 本地旧问卷（兼容）
      navigation.open({
        url: `/pages/survey-form/survey-form?type=${type}&title=${encodeURIComponent(surveyType.title)}`,
        fail: err => {
          console.error('[survey] 打开问卷失败:', err);
          wx.showToast({ title: '打开失败，请返回首页后重试', icon: 'none' });
        },
      });
    }
  },

  // ── 查看历史记录 ──
  viewHistory(e) {
    const { id } = e.currentTarget.dataset;
    navigation.open({
      url: `/pages/survey-form/survey-form?id=${id}&mode=view`,
    });
  },

  goScience() { navigation.open('/pages/science/science'); },

});
