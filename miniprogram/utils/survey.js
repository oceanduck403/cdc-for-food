// utils/survey.js
// 问卷管理 API 封装
const { request } = require('./api.js');

/**
 * 获取问卷模板列表（患者端可见）
 * @returns {Promise<Array>} 模板列表
 */
function getTemplates() {
  return request('/survey/templates');
}

/**
 * 获取单个问卷模板详情
 * @param {number} templateId 模板 ID
 * @returns {Promise<Object>} 模板详情
 */
function getTemplate(templateId) {
  return request(`/survey/templates/${templateId}`);
}

/**
 * 获取我的问卷填写记录
 * @returns {Promise<Array>} 历史记录列表
 */
function getMyResponses() {
  return request('/survey/my-responses');
}

/**
 * 提交问卷
 * @param {Object} payload
 * @param {number} payload.template_id 模板 ID
 * @param {Object} payload.answers 答案
 * @param {number} payload.total_score 总分
 * @param {string} payload.analysis AI 分析结果
 * @param {string} payload.user_name 填写人姓名
 * @param {string} payload.user_phone 填写人手机
 * @param {string} payload.submitted_at 提交时间
 * @returns {Promise<Object>}
 */
function submitResponse(payload) {
  return request({ url: '/survey/responses',
    method: 'POST',
    data: payload,
  });
}

/**
 * 获取我的单个问卷详情
 * @param {number} responseId 提交记录 ID
 * @returns {Promise<Object>}
 */
function getMyResponseDetail(responseId) {
  return request(`/survey/my-responses/${responseId}`);
}

// ═══════════════════════════════════════════════════════
// 管理员端 API
// ═══════════════════════════════════════════════════════

/**
 * 管理员：获取所有问卷模板（含未启用的）
 * @returns {Promise<Array>}
 */
function adminListTemplates() {
  return request('/survey/admin/templates');
}

/**
 * 管理员：创建问卷模板
 * @param {Object} payload
 * @param {string} payload.name 模板名称
 * @param {string} payload.type 类型标识（英文唯一）
 * @param {string} payload.description 描述
 * @param {string} payload.category 分类
 * @param {Array} payload.questions 题目列表
 * @param {boolean} payload.is_active 是否启用
 * @param {number} payload.sort_order 排序
 * @returns {Promise<Object>}
 */
function adminCreateTemplate(payload) {
  return request({ url: '/survey/admin/templates',
    method: 'POST',
    data: payload,
  });
}

/**
 * 管理员：更新问卷模板
 * @param {number} templateId 模板 ID
 * @param {Object} payload 更新字段
 * @returns {Promise<Object>}
 */
function adminUpdateTemplate(templateId, payload) {
  return request({ url: `/survey/admin/templates/${templateId}`,
    method: 'PUT',
    data: payload,
  });
}

/**
 * 管理员：停用问卷模板（软删除）
 * @param {number} templateId 模板 ID
 * @returns {Promise<Object>}
 */
function adminDeleteTemplate(templateId) {
  return request({ url: `/survey/admin/templates/${templateId}`,
    method: 'DELETE',
  });
}

/**
 * 管理员：获取所有问卷提交记录
 * @param {Object} params
 * @param {string} [params.template_type] 按类型筛选
 * @param {string} [params.keyword] 搜索关键词
 * @param {number} [params.offset] 分页偏移
 * @param {number} [params.limit] 每页条数
 * @returns {Promise<Array>}
 */
function adminListResponses(params = {}) {
  return request({ url: '/survey/admin/responses', data: params });
}

/**
 * 管理员：获取问卷提交详情（含题目和答案）
 * @param {number} responseId 提交记录 ID
 * @returns {Promise<Object>}
 */
function adminGetResponseDetail(responseId) {
  return request(`/survey/admin/responses/${responseId}`);
}

module.exports = {
  getTemplates,
  getTemplate,
  getMyResponses,
  submitResponse,
  getMyResponseDetail,
  // 管理员
  adminListTemplates,
  adminCreateTemplate,
  adminUpdateTemplate,
  adminDeleteTemplate,
  adminListResponses,
  adminGetResponseDetail,
};
