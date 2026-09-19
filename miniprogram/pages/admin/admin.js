// pages/admin/admin.js
// 管理员主页面：首发科普版仅保留用户、问卷与账号管理。
const auth = require('../../utils/auth.js');
const adminApi = require('../../utils/admin.js');
const surveyApi = require('../../utils/survey.js');

function isStrongManagedPassword(value) {
  return typeof value === 'string' && value.length >= 12 && value.length <= 72 &&
    value.trim() === value && /[a-z]/.test(value) && /[A-Z]/.test(value) &&
    /\d/.test(value) && /[^A-Za-z0-9]/.test(value);
}

Page({
  data: {
    profile: {},
    tab: 'dashboard',

    // ── 管理员自己的登录账号 ──
    showChangeAccount: false,
    accountForm: { username: '', current: '', next: '', confirm: '' },
    changingAccount: false,

    // ── 仪表盘 ──
    stats: {},

    // ── 用户管理 ──
    patients: [],
    patientKeyword: '',

    // ── 问卷管理 ──
    surveySub: 'templates',
    surveyKw: '',
    templates: [],
    filteredTemplates: [],
    surveyTypeOptions: [{ id: '', label: '全部类型' }],
    selectedSurveyType: '',
    selectedSurveyTypeLabel: '全部类型',
    responseKw: '',
    surveyResponses: [],

    // 弹窗
    showTemplateDetail: false,
    templateDetail: {},
    showTemplateEdit: false,
    editTemplate: {},
    showResponseDetail: false,
    responseDetail: {},
  },

  onLoad() {
    this.setData({ profile: wx.getStorageSync('profile') || {} });
  },

  onShow() {
    this.setData({ profile: wx.getStorageSync('profile') || {} });
    if (auth.getRole() === 'admin' && auth.getToken()) {
      this._refreshCurrentTab();
    } else {
      wx.reLaunch({ url: '/pages/admin-login/admin-login' });
    }
  },

  _refreshCurrentTab() {
    const tab = this.data.tab;
    if (tab === 'dashboard') this.loadStats();
    else if (tab === 'patients') this.reloadPatients();
    else if (tab === 'survey') this._loadSurvey();
  },

  async switchTab(e) {
    const { tab } = e.currentTarget.dataset;
    if (this.data.tab === tab) return;
    this.setData({ tab });
    this._refreshCurrentTab();
  },

  openChangeAccount() {
    this.setData({
      showChangeAccount: true,
      accountForm: { username: this.data.profile.username || '', current: '', next: '', confirm: '' },
    });
  },

  closeChangeAccount() {
    if (this.data.changingAccount) return;
    this.setData({
      showChangeAccount: false,
      accountForm: { username: '', current: '', next: '', confirm: '' },
    });
  },

  noop() {},

  onAccountFieldInput(e) {
    const { field } = e.currentTarget.dataset;
    this.setData({ [`accountForm.${field}`]: e.detail.value });
  },

  async submitChangeAccount() {
    if (this.data.changingAccount) return;
    const { username, current, next, confirm } = this.data.accountForm;
    if (!current) {
      wx.showToast({ title: '请输入原密码', icon: 'none' });
      return;
    }
    if (!/^[A-Za-z0-9_]{3,64}$/.test(username)) {
      wx.showToast({ title: '账号须为3至64位字母、数字或下划线', icon: 'none' });
      return;
    }
    if (username === this.data.profile.username && !next) {
      wx.showToast({ title: '请修改账号或填写新密码', icon: 'none' });
      return;
    }
    if (next && !isStrongManagedPassword(next)) {
      wx.showToast({ title: '密码需12位以上并含大小写、数字和符号', icon: 'none' });
      return;
    }
    if (next !== confirm) {
      wx.showToast({ title: '两次新密码不一致', icon: 'none' });
      return;
    }
    if (next === current) {
      wx.showToast({ title: '新密码不能与原密码相同', icon: 'none' });
      return;
    }

    this.setData({ changingAccount: true });
    wx.showLoading({ title: '保存中...', mask: true });
    try {
      await adminApi.changeAccount(current, username, next);
      wx.hideLoading();
      this.setData({
        showChangeAccount: false,
        accountForm: { username: '', current: '', next: '', confirm: '' },
      });
      await new Promise(resolve => wx.showModal({
        title: '账号信息已修改',
        content: '请使用更新后的账号和密码重新登录',
        showCancel: false,
        complete: resolve,
      }));
      auth.logout('/pages/admin-login/admin-login');
    } catch (err) {
      wx.hideLoading();
      wx.showToast({ title: err.message || '修改失败', icon: 'none' });
    } finally {
      this.setData({ changingAccount: false });
    }
  },

  // ───── 仪表盘 ─────
  async loadStats() {
    try {
      const stats = await adminApi.getStats();
      this.setData({ stats });
    } catch (err) { console.error(err); }
  },

  // ───── 用户管理 ─────
  onPatientKwInput(e) {
    this.setData({ patientKeyword: e.detail.value });
  },

  async reloadPatients() {
    try {
      const data = await adminApi.listPatients(this.data.patientKeyword);
      this.setData({ patients: data.patients || [] });
    } catch (err) {
      wx.showToast({ title: err.message || '加载失败', icon: 'none' });
    }
  },

  // ══════════════════════════════
  // 问卷管理
  // ══════════════════════════════

  async _loadSurvey() {
    try {
      const templates = await surveyApi.adminListTemplates();
      this.setData({
        templates,
        filteredTemplates: templates,
        surveyTypeOptions: [
          { id: '', label: '全部类型' },
          ...templates.map(t => ({ id: t.type, label: t.name })),
        ],
      });
      this._filterTemplates();
    } catch (err) {
      wx.showToast({ title: '加载问卷失败', icon: 'none' });
    }
  },

  async _loadResponses() {
    try {
      const params = {};
      if (this.data.selectedSurveyType) params.template_type = this.data.selectedSurveyType;
      if (this.data.responseKw) params.keyword = this.data.responseKw;
      const responses = await surveyApi.adminListResponses(params);
      this.setData({ surveyResponses: responses });
    } catch (err) {
      wx.showToast({ title: '加载记录失败', icon: 'none' });
    }
  },

  switchSurveySub(e) {
    const { sub } = e.currentTarget.dataset;
    this.setData({ surveySub: sub });
    if (sub === 'responses') this._loadResponses();
  },

  _filterTemplates() {
    const kw = this.data.surveyKw.toLowerCase();
    const filtered = this.data.templates.filter(t =>
      !kw || t.name.toLowerCase().includes(kw) || (t.description || '').toLowerCase().includes(kw)
    );
    this.setData({ filteredTemplates: filtered });
  },

  onSurveyKwInput(e) {
    this.setData({ surveyKw: e.detail.value });
    this._filterTemplates();
  },

  onSurveyTypeChange(e) {
    const idx = e.detail.value;
    const opt = this.data.surveyTypeOptions[idx];
    this.setData({ selectedSurveyType: opt.id, selectedSurveyTypeLabel: opt.label });
    this._loadResponses();
  },

  onResponseKwInput(e) {
    this.setData({ responseKw: e.detail.value });
  },

  // ── 查看题目 ──
  async viewTemplate(e) {
    const { id } = e.currentTarget.dataset;
    try {
      const t = this.data.templates.find(t => t.id === id);
      if (t) {
        this.setData({ showTemplateDetail: true, templateDetail: t });
      }
    } catch (err) { wx.showToast({ title: '加载失败', icon: 'none' }); }
  },

  closeTemplateDetail() {
    this.setData({ showTemplateDetail: false, templateDetail: {} });
  },

  // ── 启用/停用 ──
  async toggleTemplateActive(e) {
    const { id, current } = e.currentTarget.dataset;
    try {
      await surveyApi.adminUpdateTemplate(id, { is_active: !current });
      wx.showToast({ title: current ? '已停用' : '已启用', icon: 'success' });
      await this._loadSurvey();
    } catch (err) {
      wx.showToast({ title: err.message || '操作失败', icon: 'none' });
    }
  },

  // ── 新增模板 ──
  openAddTemplate() {
    this.setData({
      showTemplateEdit: true,
      editTemplate: { name: '', type: '', description: '', category: '健康管理', is_active: true, questions: [] },
    });
  },

  // ── 编辑模板 ──
  async openEditTemplate(e) {
    const { id } = e.currentTarget.dataset;
    const t = this.data.templates.find(t => t.id === id);
    if (!t) return;
    this.setData({
      showTemplateEdit: true,
      editTemplate: {
        id: t.id,
        name: t.name,
        type: t.type,
        description: t.description,
        category: t.category,
        is_active: t.is_active,
        questions: t.questions,
      },
    });
  },

  onEditTemplateField(e) {
    const { field } = e.currentTarget.dataset;
    this.setData({ [`editTemplate.${field}`]: e.detail.value });
  },

  async submitTemplateEdit() {
    const t = this.data.editTemplate;
    if (!t.name || !t.type) {
      wx.showToast({ title: '名称和类型不能为空', icon: 'none' }); return;
    }
    try {
      if (t.id) {
        await surveyApi.adminUpdateTemplate(t.id, {
          name: t.name, description: t.description, category: t.category, is_active: t.is_active,
        });
        wx.showToast({ title: '更新成功', icon: 'success' });
      } else {
        await surveyApi.adminCreateTemplate({
          name: t.name, type: t.type, description: t.description,
          category: t.category || '健康管理', is_active: t.is_active !== false, questions: [],
        });
        wx.showToast({ title: '创建成功', icon: 'success' });
      }
      this.setData({ showTemplateEdit: false, editTemplate: {} });
      await this._loadSurvey();
    } catch (err) {
      wx.showToast({ title: err.message || '操作失败', icon: 'none' });
    }
  },

  closeTemplateEdit() {
    this.setData({ showTemplateEdit: false, editTemplate: {} });
  },

  // ── 提交记录详情 ──
  async viewResponseDetail(e) {
    const { id } = e.currentTarget.dataset;
    wx.showLoading({ title: '加载中...', mask: true });
    try {
      const detail = await surveyApi.adminGetResponseDetail(id);
      this.setData({ showResponseDetail: true, responseDetail: detail });
    } catch (err) {
      wx.showToast({ title: err.message || '加载失败', icon: 'none' });
    } finally {
      wx.hideLoading();
    }
  },

  closeResponseDetail() {
    this.setData({ showResponseDetail: false, responseDetail: {} });
  },

  // ───── 退出 ─────
  async logout() {
    const res = await new Promise(r => wx.showModal({ title: '退出登录', content: '确定退出吗？', success: r }));
    if (res.confirm) auth.logout();
  },
});
