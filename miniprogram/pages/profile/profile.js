// pages/profile/profile.js
const { request } = require('../../utils/request.js');
const storage = require('../../utils/storage.js');
const { bmrMifflin, tdee } = require('../../utils/nutrition.js');

const activityOptions = [
  { value: 'sedentary', label: '久坐（几乎不运动）' },
  { value: 'light',     label: '轻度活动（每周1-3天）' },
  { value: 'moderate',   label: '中度活动（每周3-5天）' },
  { value: 'active',    label: '高度活动（每天运动）' },
];

const defaultProfile = {
  age: '',
  sex: 'male',
  heightCm: '',
  weightKg: '',
  activityLevel: 'light',
  activityLevelLabel: '轻度活动（每周1-3天）',
  healthNotes: '',
};

function calcBmiResult(h, w) {
  if (!h || !w) return { show: false };
  const bmi = w / ((h / 100) * (h / 100));
  const v = bmi.toFixed(1);
  if (bmi < 18.5)  return { show: true, value: v, label: '偏瘦', cls: 'under' };
  if (bmi < 24)     return { show: true, value: v, label: '正常', cls: 'normal' };
  if (bmi < 28)     return { show: true, value: v, label: '超重', cls: 'over' };
  return              { show: true, value: v, label: '肥胖', cls: 'obese' };
}

Page({
  data: {
    profile: { ...defaultProfile },
    activityOptions,
    activityIndex: 1,
    sexIndex: 0,
    tdee: null,
    saving: false,
    bmiResult: { show: false },
  },

  onShow() {
    const cached = storage.get('profile');
    if (cached) {
      this.applyProfile(cached);
    }
    this.loadProfile();
  },

  applyProfile(p) {
    const merged = { ...defaultProfile, ...p };
    const actIdx = Math.max(0, activityOptions.findIndex((o) => o.value === merged.activityLevel));
    const bmiResult = calcBmiResult(Number(merged.heightCm), Number(merged.weightKg));
    this.setData({
      profile: merged,
      activityIndex: actIdx,
      sexIndex: merged.sex === 'female' ? 1 : 0,
      bmiResult,
    }, () => this.recalc());
  },

  loadProfile() {
    request({ url: '/users/me', showLoading: false })
      .then((data) => { if (data) this.applyProfile(data); })
      .catch(() => {});
  },

  onInput(e) {
    const { field } = e.currentTarget.dataset;
    const merged = { ...this.data.profile, [field]: e.detail.value };
    this.setData({
      [`profile.${field}`]: e.detail.value,
      bmiResult: calcBmiResult(Number(merged.heightCm), Number(merged.weightKg)),
    }, () => this.recalc());
  },

  onPickSex(e) {
    const sex = e.detail.value === 1 ? 'female' : 'male';
    this.setData({ 'profile.sex': sex, sexIndex: e.detail.value });
  },

  onPickActivity(e) {
    const idx = Number(e.detail.value) || 0;
    const opt = activityOptions[idx];
    this.setData({
      'profile.activityLevel': opt.value,
      'profile.activityLevelLabel': opt.label,
      activityIndex: idx,
    }, () => this.recalc());
  },

  recalc() {
    const { age, sex, heightCm, weightKg, activityLevel } = this.data.profile;
    if (age && heightCm && weightKg) {
      const bmr = bmrMifflin({
        sex,
        weightKg: Number(weightKg),
        heightCm: Number(heightCm),
        age: Number(age)
      });
      const energy = tdee(bmr, activityLevel);
      this.setData({ tdee: Math.round(energy) });
    } else {
      this.setData({ tdee: null });
    }
  },

  save() {
    this.setData({ saving: true });
    request({
      url: '/users/me',
      method: 'PUT',
      data: this.data.profile,
      showLoading: false
    })
      .then(() => {
        storage.set('profile', this.data.profile);
        wx.showToast({ title: '已保存', icon: 'success' });
      })
      .catch(() => storage.set('profile', this.data.profile))
      .finally(() => this.setData({ saving: false }));
  }
});

Page({
  data: {
    profile: { ...defaultProfile },
    activityOptions,
    activityIndex: 1,
    sexIndex: 0,
    tdee: null,
    saving: false
  },

  onShow() {
    const cached = storage.get('profile');
    if (cached && (cached.age || cached.heightCm)) {
      this.applyProfile(cached);
    }
    this.loadProfile();
  },

  applyProfile(p) {
    const merged = { ...defaultProfile, ...p };
    this.setData({
      profile: merged,
      activityIndex: Math.max(0, activityOptions.findIndex((o) => o.value === merged.activityLevel)),
      sexIndex: merged.sex === 'female' ? 1 : 0
    }, () => this.recalc());
  },

  loadProfile() {
    request({ url: '/users/me', showLoading: false })
      .then((data) => {
        if (!data) return;
        this.applyProfile(data);
      })
      .catch(() => {});
  },

  onInput(e) {
    const { field } = e.currentTarget.dataset;
    this.setData({ [`profile.${field}`]: e.detail.value }, () => this.recalc());
  },

  onPickSex(e) {
    this.setData({
      'profile.sex': e.detail.value === 1 ? 'female' : 'male',
      sexIndex: e.detail.value
    });
  },

  onPickActivity(e) {
    const idx = Number(e.detail.value) || 0;
    const opt = activityOptions[idx] || activityOptions[0];
    this.setData({
      'profile.activityLevel': opt.value,
      activityIndex: idx
    });
  },

  recalc() {
    const { age, sex, heightCm, weightKg, activityLevel } = this.data.profile;
    if (age && heightCm && weightKg) {
      const bmr = bmrMifflin({
        sex,
        weightKg: Number(weightKg),
        heightCm: Number(heightCm),
        age: Number(age)
      });
      const energy = tdee(bmr, activityLevel);
      const opt = activityOptions.find((o) => o.value === activityLevel);
      this.setData({
        tdee: energy,
        'profile.activityLevelLabel': opt ? opt.label : activityLevel
      });
    } else {
      this.setData({ tdee: null });
    }
  },

  save() {
    this.setData({ saving: true });
    request({
      url: '/users/me',
      method: 'PUT',
      data: this.data.profile,
      showLoading: false
    })
      .then(() => {
        storage.set('profile', this.data.profile);
        wx.showToast({ title: '已保存' });
      })
      .catch(() => storage.set('profile', this.data.profile))
      .finally(() => this.setData({ saving: false }));
  }
});
