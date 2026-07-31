// pages/profile/profile.js
const { request } = require('../../utils/request.js');
const storage = require('../../utils/storage.js');
const { bmrMifflin, tdee } = require('../../utils/nutrition.js');

const activityOptions = [
  { value: 'sedentary', label: '久坐' },
  { value: 'light', label: '轻度活动' },
  { value: 'moderate', label: '中度活动' },
  { value: 'active', label: '高度活动' }
];

const defaultProfile = {
  age: '',
  sex: 'male',
  heightCm: '',
  weightKg: '',
  activityLevel: 'light',
  healthNotes: ''
};

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
