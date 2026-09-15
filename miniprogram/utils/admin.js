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

function listDoctors(keyword = '') {
  const url = keyword
    ? `/admin/doctors?keyword=${encodeURIComponent(keyword)}`
    : '/admin/doctors';
  return request({ url });
}

function createDoctor(data) {
  return request({
    url: '/admin/doctors',
    method: 'POST',
    data,
  });
}

function updateDoctor(id, data) {
  return request({
    url: `/admin/doctors/${id}`,
    method: 'PUT',
    data,
  });
}

function deleteDoctor(id) {
  return request({
    url: `/admin/doctors/${id}`,
    method: 'DELETE',
  });
}

function listPatients(keyword = '') {
  const url = keyword
    ? `/admin/patients?keyword=${encodeURIComponent(keyword)}`
    : '/admin/patients';
  return request({ url });
}

function listAssignments() {
  return request({ url: '/admin/assignments' });
}

function createAssignment(patient_id, doctor_id) {
  return request({
    url: '/admin/assignments',
    method: 'POST',
    data: { patient_id, doctor_id },
  });
}

function listChats(params = {}) {
  const q = ['patient_id', 'doctor_id', 'limit'].filter(key => params[key])
    .map(key => `${key}=${encodeURIComponent(params[key])}`).join('&');
  return request({ url: `/admin/chats?${q}` });
}

module.exports = {
  getStats,
  changeAccount,
  listDoctors,
  createDoctor,
  updateDoctor,
  deleteDoctor,
  listPatients,
  listAssignments,
  createAssignment,
  listChats,
};
