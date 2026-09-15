// 页面导航统一处理 tabBar 和普通页面，并暴露失败原因。
const tabPages = new Set(['/pages/survey/survey', '/pages/checkin/checkin', '/pages/consult/consult', '/pages/science/science', '/pages/mine/mine']);
function report(err) {
  console.error('[navigation]', err);
  wx.showToast({ title: /not found|不存在/.test(err.errMsg || '') ? '页面未加载，请重新编译后重试' : '页面打开失败，请返回首页重试', icon: 'none' });
}
function open(options) {
  const args = typeof options === 'string' ? { url: options } : options;
  const fail = err => {
    if (/limit|层级|page stack/i.test(err.errMsg || '')) {
      wx.redirectTo({ ...args, fail: args.fail || report });
    } else (args.fail || report)(err);
  };
  if (tabPages.has(args.url.split('?')[0])) wx.switchTab({ ...args, fail: args.fail || report });
  else wx.navigateTo({ ...args, fail });
}
function login(role = 'patient') {
  open(role === 'admin' ? '/pages/admin-login/admin-login' : `/pages/login/login?role=${role}`);
}
module.exports = { open, login, report };
