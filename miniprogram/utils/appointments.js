const { request } = require('./api.js');
module.exports = {
  mine: () => request('/appointments/mine'),
  book: () => request({ url: '/appointments/mine', method: 'POST' }),
  cancel: () => request({ url: '/appointments/mine', method: 'DELETE' }),
  heartbeat: () => request({ url: '/appointments/heartbeat', method: 'POST' }),
  dispatch: () => request('/appointments/dispatch'),
  adjust: (id, action, doctor_id) => request({ url: `/appointments/dispatch/${id}`, method: 'POST', data: { action, doctor_id } }),
  availability: (id, available) => request({ url: `/appointments/doctors/${id}`, method: 'PUT', data: { available } }),
};
