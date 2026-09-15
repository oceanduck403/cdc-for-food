// Keep transport diagnostics available without showing raw wx.request errors to users.
function networkError(err) {
  const detail = (err && err.errMsg) || '';
  let message = '暂时无法连接服务，请稍后重试';
  if (/timeout/i.test(detail)) message = '连接超时，请检查网络后重试';
  else if (/url not in domain list|invalid url|ssl|certificate/i.test(detail)) {
    message = '服务连接配置异常，请联系管理员';
  }
  const error = new Error(message);
  error.code = 'NETWORK_ERROR';
  error.detail = detail;
  return error;
}

module.exports = { networkError };
