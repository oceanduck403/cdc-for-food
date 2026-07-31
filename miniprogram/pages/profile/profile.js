// pages/profile/profile.js
const { request } = require('../../utils/request.js');
const { bmrMifflin, tdee } = require('../../utils/nutrition.js');

const activityOptions = [
  { value: 'sedentary', label: '久坐' },
  { value: 'light', label: '轻度活动' },
  { value: 'moderate', label: '中度活动' },
  { value: 'active', label: '高度活动' }
];

Page({
  data: {
    profile: {
      age: '',
      sex: 'male',
      heightCm: '',
      weightKg: '',
      activityLevel: 'light',
      healthNotes: ''
    },
    activityOptions,
    tdee: null,
    saving: false
  },

  onShow() {
    this.loadProfile();
  },

  loadProfile() {
    request({ url: '/users/me', showLoading: false })
      .then((data) => {
        if (!data) return;
        const p = { ...this.data.profile, ...data };
        this.setData({ profile: p });
        this.recalc();
      })
      .catch(() => {});
  },

  onInput(e) {
    const { field } = e.currentTarget.dataset;
    this.setData({ [`profile.${field}`]: e.detail.value }, () => this.recalc());
  },

  onPick(e) {
    const { field } = e.currentTarget.dataset;
    this.setData({ [`profile.${field}`]: e.detail.value });
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
      this.setData({ tdee: energy });
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
        wx.showToast({ title: '已保存' });
      })
      .catch(() => {})
      .finally(() => this.setData({ saving: false }));
  }
});