// pages/admin/admin.js
// 管理员主页面（6 个 tab 一体化）
const auth = require('../../utils/auth.js');
const adminApi = require('../../utils/admin.js');
const surveyApi = require('../../utils/survey.js');

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

    // ── 医生管理 ──
    doctors: [],
    doctorKeyword: '',
    showAddDoctor: false,
    newDoctor: { real_name: '', username: '', password: '', department: '', title: '', intro: '' },

    // ── 重置密码 ──
    showResetPassword: false,
    resetTarget: { id: 0, name: '' },
    newPassword: '',

    // ── 患者管理 ──
    patients: [],
    patientKeyword: '',

    // ── 分配 ──
    assignments: [],
    patientOptions: [],
    doctorOptions: [],
    assignForm: { patient_id: 0, patient_label: '', doctor_id: 0, doctor_label: '' },

    // ── 聊天 ──
    chats: [],

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
    else if (tab === 'doctors') this.reloadDoctors();
    else if (tab === 'patients') this.reloadPatients();
    else if (tab === 'assignments') this.loadAssignments();
    else if (tab === 'chats') this.loadChats();
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
    if (next && next.length < 8) {
      wx.showToast({ title: '新密码至少8位', icon: 'none' });
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

  // ───── 医生管理 ─────
  onDoctorKwInput(e) {
    this.setData({ doctorKeyword: e.detail.value });
  },

  async reloadDoctors() {
    try {
      const data = await adminApi.listDoctors(this.data.doctorKeyword);
      this.setData({ doctors: data.doctors || [] });
    } catch (err) {
      wx.showToast({ title: err.message || '加载失败', icon: 'none' });
    }
  },

  openAddDoctor() {
    this.setData({
      showAddDoctor: true,
      newDoctor: { real_name: '', username: '', password: '', department: '', title: '', intro: '' },
    });
  },

  closeAddDoctor() {
    this.setData({ showAddDoctor: false });
  },

  onNewDoctorField(e) {
    const { field } = e.currentTarget.dataset;
    this.setData({ [`newDoctor.${field}`]: e.detail.value });
  },

  async submitAddDoctor() {
    const { real_name, username, password } = this.data.newDoctor;
    if (!real_name || !username || !password) {
      wx.showToast({ title: '请填写姓名/账号/密码', icon: 'none' }); return;
    }
    try {
      await adminApi.createDoctor(this.data.newDoctor);
      wx.showToast({ title: '创建成功', icon: 'success' });
      this.setData({ showAddDoctor: false });
      await this.reloadDoctors();
      await this.loadStats();
    } catch (err) {
      wx.showToast({ title: err.message || '创建失败', icon: 'none' });
    }
  },

  async toggleDoctorAvailable(e) {
    const { id, current } = e.currentTarget.dataset;
    try {
      await adminApi.updateDoctor(id, { is_available: !current });
      wx.showToast({ title: '已更新', icon: 'success' });
      await this.reloadDoctors();
    } catch (err) {
      wx.showToast({ title: err.message || '操作失败', icon: 'none' });
    }
  },

  openResetPassword(e) {
    const { id, name } = e.currentTarget.dataset;
    this.setData({ showResetPassword: true, resetTarget: { id, name }, newPassword: '' });
  },

  closeResetPassword() {
    this.setData({ showResetPassword: false });
  },

  onNewPasswordInput(e) {
    this.setData({ newPassword: e.detail.value });
  },

  async submitResetPassword() {
    if (!this.data.newPassword || this.data.newPassword.length < 6) {
      wx.showToast({ title: '密码至少6位', icon: 'none' }); return;
    }
    try {
      await adminApi.updateDoctor(this.data.resetTarget.id, { new_password: this.data.newPassword });
      wx.showToast({ title: '密码已重置', icon: 'success' });
      this.setData({ showResetPassword: false });
    } catch (err) {
      wx.showToast({ title: err.message || '重置失败', icon: 'none' });
    }
  },

  async deleteDoctor(e) {
    const { id, name } = e.currentTarget.dataset;
    const res = await new Promise(r => wx.showModal({
      title: '禁用医生', content: `确定禁用 ${name} 吗？禁用后无法登录`, success: r,
    }));
    if (res.confirm) {
      try {
        await adminApi.deleteDoctor(id);
        wx.showToast({ title: '已禁用', icon: 'success' });
        await this.reloadDoctors();
        await this.loadStats();
      } catch (err) {
        wx.showToast({ title: err.message || '操作失败', icon: 'none' });
      }
    }
  },

  // ───── 患者管理 ─────
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

  // ───── 分配管理 ─────
  async loadAssignments() {
    try {
      const [assignData, patData, docData] = await Promise.all([
        adminApi.listAssignments(),
        adminApi.listPatients(),
        adminApi.listDoctors(),
      ]);
      const assignments = assignData.assignments || [];
      const patients = patData.patients || [];
      const patientOptions = patients.map(p => ({
        id: p.id, label: `${p.real_name || p.nickname || '用户' + p.id} (ID:${p.id})`,
      }));
      const doctorOptions = (docData.doctors || []).filter(d => d.is_active).map(d => ({
        id: d.id, label: `${d.real_name} - ${d.department || ''} ${d.title || ''}`,
      }));
      this.setData({ assignments, patientOptions, doctorOptions });
    } catch (err) { console.error(err); }
  },

  onAssignPatient(e) {
    const idx = e.detail.value;
    const p = this.data.patientOptions[idx];
    this.setData({ 'assignForm.patient_id': p.id, 'assignForm.patient_label': p.label });
  },

  onAssignDoctor(e) {
    const idx = e.detail.value;
    const d = this.data.doctorOptions[idx];
    this.setData({ 'assignForm.doctor_id': d.id, 'assignForm.doctor_label': d.label });
  },

  async submitAssignment() {
    const { patient_id, doctor_id } = this.data.assignForm;
    if (!patient_id || !doctor_id) {
      wx.showToast({ title: '请选择患者和医生', icon: 'none' }); return;
    }
    try {
      await adminApi.createAssignment(patient_id, doctor_id);
      wx.showToast({ title: '分配成功', icon: 'success' });
      this.setData({ 'assignForm.patient_id': 0, 'assignForm.patient_label': '', 'assignForm.doctor_id': 0, 'assignForm.doctor_label': '' });
      await this.loadAssignments();
      await this.loadStats();
    } catch (err) {
      wx.showToast({ title: err.message || '分配失败', icon: 'none' });
    }
  },

  // ───── 聊天记录 ─────
  async loadChats() {
    try {
      const data = await adminApi.listChats({ limit: 200 });
      this.setData({ chats: (data.messages || []).map(item => ({...item, displayTime: this.formatTime(item.created_at)})) });
    } catch (err) { console.error(err); }
  },

  formatTime(iso) {
    if (!iso) return '';
    const d = new Date(iso);
    const pad = n => String(n).padStart(2, '0');
    return `${d.getMonth() + 1}/${d.getDate()} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
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
      editTemplate: { name: '', type: '', description: '', category: '体重管理', is_active: true, questions: [] },
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
          category: t.category || '体重管理', is_active: t.is_active !== false, questions: [],
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
