// pages/profile/profile.js
const { request } = require('../../utils/request.js');
const storage = require('../../utils/storage.js');
const config = require('../../utils/config.js');
const transport = require('../../utils/transport.js');
const { bmrMifflin, tdee } = require('../../utils/nutrition.js');

const activityOptions = [
  { value: 'sedentary', label: '久坐（几乎不运动）' },
  { value: 'light', label: '轻度活动（每周1-3天）' },
  { value: 'moderate', label: '中度活动（每周3-5天）' },
  { value: 'active', label: '高度活动（每天运动）' },
];

const defaultProfile = {
  nickname: '', age: '', sex: 'male', heightCm: '', weightKg: '',
  activityLevel: 'light', activityLevelLabel: '轻度活动（每周1-3天）', healthNotes: '',
};

function avatarUrl(path) {
  if (!path) return '';
  if (/^(https?:|wxfile:|cloud:|data:)/i.test(path)) return path;
  const base = transport.getDirectBaseUrl ? transport.getDirectBaseUrl() : config.baseUrl;
  if (path.startsWith('/') && base) return `${base}${path}`;
  return '';
}

function calcBmiResult(h, w) {
  if (!h || !w) return { show: false };
  const bmi = w / ((h / 100) * (h / 100));
  const v = bmi.toFixed(1);
  if (bmi < 18.5) return { show: true, value: v, label: '偏瘦', cls: 'under' };
  if (bmi < 24) return { show: true, value: v, label: '正常', cls: 'normal' };
  if (bmi < 28) return { show: true, value: v, label: '超重', cls: 'over' };
  return { show: true, value: v, label: '肥胖', cls: 'obese' };
}

function cacheProfile(profile) {
  const merged = { ...(storage.get('profile') || {}), ...profile };
  storage.set('profile', merged);
  storage.set('userInfo', merged);
  const app = getApp();
  if (app && app.globalData) {
    app.globalData.profile = merged;
    app.globalData.userInfo = merged;
  }
}

Page({
  data: {
    profile: { ...defaultProfile }, avatarDisplayUrl: '', activityOptions,
    activityIndex: 1, sexIndex: 0, tdee: null, saving: false,
    savingAvatar: false, savingName: false, bmiResult: { show: false },
  },

  onShow() {
    const cached = storage.get('profile');
    if (cached) this.applyProfile(cached);
    if (storage.get('token')) this.loadProfile();
  },

  applyProfile(profile) {
    const merged = { ...defaultProfile, ...profile };
    const activityIndex = Math.max(0, activityOptions.findIndex((o) => o.value === merged.activityLevel));
    merged.activityLevelLabel = activityOptions[activityIndex].label;
    this.setData({
      profile: merged, avatarDisplayUrl: avatarUrl(merged.avatar), activityIndex,
      sexIndex: merged.sex === 'female' ? 1 : 0,
      bmiResult: calcBmiResult(Number(merged.heightCm), Number(merged.weightKg)),
    }, () => this.recalc());
    if (merged.avatar && !this.data.avatarDisplayUrl && transport.resolveMediaUrl) {
      transport.resolveMediaUrl(merged.avatar).then((resolved) => {
        if (this.data.profile.avatar === merged.avatar) this.setData({ avatarDisplayUrl: resolved });
      }).catch(() => {});
    }
  },

  loadProfile() {
    request({ url: '/users/me', showLoading: false, silent: true })
      .then((profile) => {
        if (profile && profile.id) {
          cacheProfile(profile);
          if (!this._dirtyFields || !this._dirtyFields.size) this.applyProfile(profile);
        }
      })
      .catch(() => {});
  },

  onAvatarError() { this.setData({ avatarDisplayUrl: '' }); },

  chooseAvatar() {
    if (!storage.get('token')) {
      wx.showToast({ title: '请先登录', icon: 'none' });
      return;
    }
    if (this.data.savingAvatar) return;
    wx.showActionSheet({
      itemList: ['从相册选取', '拍照'],
      success: ({ tapIndex }) => this.pickAvatar(tapIndex === 1 ? 'camera' : 'album'),
    });
  },

  pickAvatar(sourceType) {
    wx.chooseMedia({
      count: 1, mediaType: ['image'], sourceType: [sourceType],
      success: ({ tempFiles }) => {
        const selected = tempFiles && tempFiles[0];
        if (!selected || !selected.tempFilePath) return;
        if (selected.size > 5 * 1024 * 1024) {
          wx.compressImage({
            src: selected.tempFilePath, quality: 78, compressedWidth: 1600,
            success: ({ tempFilePath }) => {
              if (tempFilePath) this.uploadAvatar(tempFilePath);
              else wx.showToast({ title: '照片压缩失败，请换一张', icon: 'none' });
            },
            fail: () => wx.showToast({ title: '照片压缩失败，请换一张', icon: 'none' }),
          });
          return;
        }
        this.uploadAvatar(selected.tempFilePath);
      },
    });
  },

  uploadAvatar(filePath) {
    this.setData({ savingAvatar: true });
    wx.showLoading({ title: '保存头像中', mask: true });
    transport.uploadFile({
      url: '/users/me/avatar', filePath, name: 'file',
      header: { Authorization: `Bearer ${storage.get('token')}` }, timeout: 20000,
      success: (result) => {
        let payload;
        try { payload = JSON.parse(result.data); } catch (_) { payload = null; }
        if (result.statusCode < 200 || result.statusCode >= 300 || !payload || !payload.avatar) {
          const message = result.statusCode === 401 ? '请重新登录' : (payload && payload.message) || '头像保存失败';
          wx.showToast({ title: message, icon: 'none' });
          return;
        }
        const draft = { ...payload };
        if (this._dirtyFields) {
          for (const field of this._dirtyFields) draft[field] = this.data.profile[field];
        }
        cacheProfile(payload);
        this.applyProfile(draft);
        wx.showToast({ title: '头像已更新', icon: 'success' });
      },
      fail: () => wx.showToast({ title: '网络异常，请稍后重试', icon: 'none' }),
      complete: () => {
        wx.hideLoading();
        this.setData({ savingAvatar: false });
      },
    });
  },

  onInput(e) {
    const { field } = e.currentTarget.dataset;
    const value = e.detail.value;
    if (!this._dirtyFields) this._dirtyFields = new Set();
    this._dirtyFields.add(field);
    const merged = { ...this.data.profile, [field]: value };
    this.setData({
      [`profile.${field}`]: value,
      bmiResult: calcBmiResult(Number(merged.heightCm), Number(merged.weightKg)),
    }, () => this.recalc());
  },

  onPickSex(e) {
    const index = Number(e.detail.value) || 0;
    if (!this._dirtyFields) this._dirtyFields = new Set();
    this._dirtyFields.add('sex');
    this.setData({ 'profile.sex': index === 1 ? 'female' : 'male', sexIndex: index }, () => this.recalc());
  },

  onPickActivity(e) {
    const index = Number(e.detail.value) || 0;
    const option = activityOptions[index] || activityOptions[0];
    if (!this._dirtyFields) this._dirtyFields = new Set();
    this._dirtyFields.add('activityLevel');
    this.setData({
      'profile.activityLevel': option.value, 'profile.activityLevelLabel': option.label,
      activityIndex: index,
    }, () => this.recalc());
  },

  recalc() {
    const { age, sex, heightCm, weightKg, activityLevel } = this.data.profile;
    if (age && heightCm && weightKg) {
      const bmr = bmrMifflin({ sex, weightKg: Number(weightKg), heightCm: Number(heightCm), age: Number(age) });
      this.setData({ tdee: Math.round(tdee(bmr, activityLevel)) });
    } else {
      this.setData({ tdee: null });
    }
  },

  saveNickname() {
    if (!storage.get('token')) {
      wx.showToast({ title: '请先登录', icon: 'none' });
      return;
    }
    if (this.data.savingName || this.data.savingAvatar || this.data.saving) return;
    const nickname = String(this.data.profile.nickname || '').trim();
    if (!nickname || nickname.length > 20 || /[\x00-\x1f<>]/.test(nickname)) {
      wx.showToast({ title: '请输入 1 到 20 字的昵称', icon: 'none' });
      return;
    }
    this.setData({ savingName: true });
    return request({ url: '/users/me', method: 'PUT', data: { nickname }, showLoading: false })
      .then((saved) => {
        const draft = { ...saved };
        if (this._dirtyFields) {
          for (const field of this._dirtyFields) {
            if (field !== 'nickname') draft[field] = this.data.profile[field];
          }
          this._dirtyFields.delete('nickname');
        }
        cacheProfile(saved);
        this.applyProfile(draft);
        wx.showToast({ title: '昵称已更新', icon: 'success' });
      })
      .catch(() => {})
      .finally(() => this.setData({ savingName: false }));
  },

  save() {
    if (!storage.get('token')) {
      wx.showToast({ title: '请先登录', icon: 'none' });
      return;
    }
    if (this.data.saving || this.data.savingAvatar || this.data.savingName) return;
    const profile = this.data.profile;
    const nickname = String(profile.nickname || '').trim();
    if ((this._dirtyFields && this._dirtyFields.has('nickname') && !nickname) ||
        (nickname && (nickname.length > 20 || /[\x00-\x1f<>]/.test(nickname)))) {
      wx.showToast({ title: '昵称请控制在 20 字以内', icon: 'none' });
      return;
    }
    const data = {
      age: profile.age || null, sex: profile.sex,
      heightCm: profile.heightCm || null, weightKg: profile.weightKg || null,
      activityLevel: profile.activityLevel, healthNotes: profile.healthNotes || '',
    };
    if (nickname) data.nickname = nickname;
    this.setData({ saving: true });
    return request({ url: '/users/me', method: 'PUT', data, showLoading: false })
      .then((saved) => {
        this._dirtyFields = new Set();
        cacheProfile(saved);
        this.applyProfile(saved);
        wx.showToast({ title: '已保存', icon: 'success' });
      })
      .catch(() => {})
      .finally(() => this.setData({ saving: false }));
  },
});
