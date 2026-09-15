// utils/storage.js
module.exports = {
  set(key, value) {
    try { wx.setStorageSync(key, value); } catch (e) {}
  },
  get(key, fallback) {
    try {
      const v = wx.getStorageSync(key);
      return v === '' || v === undefined || v === null ? fallback : v;
    } catch (e) { return fallback; }
  },
  remove(key) {
    try { wx.removeStorageSync(key); } catch (e) {}
  },
  clearUserData() {
    ['token', 'role', 'profile', 'userInfo', 'history', 'start_free_appointment'].forEach((k) => this.remove(k));
  }
};
