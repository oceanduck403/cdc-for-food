// utils/chat.js
// 聊天相关 API 封装
const { request } = require('./api.js');
const transport = require('./transport.js');

/**
 * 患者：获取/自动分配我的医生
 */
function fetchMyDoctor() {
  return request({ url: '/chat/my-doctor' });
}

/**
 * 发送聊天消息
 */
function sendMessage({ assignment_id, content, msg_type = 'text', image_url = null }) {
  return request({
    url: '/chat/send',
    method: 'POST',
    data: {
      assignment_id,
      content,
      msg_type,
      image_url,
    },
  });
}

/**
 * 拉取聊天记录
 */
function fetchMessages({ assignment_id, limit = 50, before_id = null }) {
  return request({
    url: `/chat/messages?assignment_id=${assignment_id}&limit=${limit}${before_id ? `&before_id=${before_id}` : ''}`,
  });
}

/**
 * 标记已读
 */
function markRead({ assignment_id }) {
  return request({
    url: `/chat/read?assignment_id=${assignment_id}`,
    method: 'POST',
  });
}

/**
 * 医生：获取患者列表（支持搜索）
 */
function fetchDoctorPatients(keyword = '') {
  const url = keyword
    ? `/chat/doctor/patients?keyword=${encodeURIComponent(keyword)}`
    : '/chat/doctor/patients';
  return request({ url });
}

/**
 * 医生：获取患者详细信息
 */
function fetchPatientDetail(patient_id) {
  return request({ url: `/chat/doctor/patient-detail/${patient_id}` });
}

/**
 * 医生：邀请另一位医生会诊
 */
function inviteConsult({ assignment_id, target_doctor_id, note = '' }) {
  return request({
    url: '/chat/consult/invite',
    method: 'POST',
    data: { assignment_id, target_doctor_id, note },
  });
}

/**
 * 医生：回应会诊邀请
 */
function respondConsult({ message_id, accept }) {
  return request({
    url: '/chat/consult/respond',
    method: 'POST',
    data: { message_id, accept },
  });
}

/**
 * 医生：获取可会诊的医生列表
 */
function fetchAvailableDoctors() {
  return request({ url: '/chat/consult/available-doctors' });
}

/**
 * 上传聊天图片
 */
function uploadChatImage(filePath, assignmentId) {
  if (!Number.isInteger(Number(assignmentId)) || Number(assignmentId) < 1) {
    return Promise.reject(new Error('聊天会话无效，请刷新后重试'));
  }
  const token = wx.getStorageSync('token');
  return new Promise((resolve, reject) => {
    transport.uploadFile({
      url: '/chat/upload-image',
      filePath,
      name: 'file',
      formData: { assignment_id: String(assignmentId) },
      header: { 'Authorization': `Bearer ${token}` },
      success: res => {
        try {
          const data = JSON.parse(res.data);
          if (res.statusCode >= 200 && res.statusCode < 300 && data.url) resolve(data);
          else reject(new Error(data.detail || data.message || '上传失败'));
        } catch (e) {
          reject(new Error('解析响应失败'));
        }
      },
      fail: err => reject(new Error(err.errMsg || '上传失败')),
    });
  });
}

module.exports = {
  fetchMyDoctor,
  sendMessage,
  fetchMessages,
  markRead,
  fetchDoctorPatients,
  fetchPatientDetail,
  inviteConsult,
  respondConsult,
  fetchAvailableDoctors,
  uploadChatImage,
};
