// utils/admin.js
// 管理员 API
const { request } = require('./api.js');

function getStats() {
  return request({ url: '/admin/stats' });
}

function changeAccount(currentPassword, newUsername, newPassword) {
  return request({
    url: '/admin/account',
    method: 'POST',
    data: {
      current_password: currentPassword,
      new_username: newUsername,
      ...(newPassword ? { new_password: newPassword } : {}),
    },
  });
}

function listPatients(keyword = '') {
  const url = keyword
    ? `/admin/patients?keyword=${encodeURIComponent(keyword)}`
    : '/admin/patients';
  return request({ url });
}

module.exports = {
  getStats,
  changeAccount,
  listPatients,
};
