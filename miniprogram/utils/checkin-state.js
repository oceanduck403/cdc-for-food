function dayKey(date = new Date()) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}
function summarize(records, now = new Date()) {
  const today = dayKey(now);
  const days = new Set(records.map(r => r.day || r.date));
  const state = { diet: false, exercise: false, water: false };
  records.filter(r => (r.day || r.date) === today).forEach(r => { if (r.type in state) state[r.type] = true; });
  let continueDays = 0;
  const cursor = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  if (!days.has(today)) cursor.setDate(cursor.getDate() - 1);
  while (days.has(dayKey(cursor))) { continueDays++; cursor.setDate(cursor.getDate() - 1); }
  return { todayCheckin: state, stats: { totalDays: days.size, continueDays, totalActions: records.length } };
}
function positiveFeedback(records, now = new Date(), lastAction = '') {
  const todayCheckin = summarize(records, now).todayCheckin;
  const doneCount = ['diet', 'exercise', 'water'].filter(type => todayCheckin[type]).length;
  const validDays = new Set(records
    .filter(record => ['diet', 'exercise', 'water'].includes(record.type))
    .map(record => record.day || record.date));
  const weekTrail = [];
  for (let offset = 6; offset >= 0; offset--) {
    const date = new Date(now.getFullYear(), now.getMonth(), now.getDate() - offset);
    weekTrail.push({
      label: offset === 0 ? '今天' : `周${['日', '一', '二', '三', '四', '五', '六'][date.getDay()]}`,
      active: validDays.has(dayKey(date)),
      isToday: offset === 0,
    });
  }
  const weekDays = weekTrail.filter(day => day.active).length;
  const titles = [
    '今天，从一小步开始',
    '已点亮 1 件健康小事',
    '已点亮 2 件健康小事',
    '今天的 3 件小事都完成啦',
  ];
  const messages = [
    '从膳食、运动、饮水中选一项，完成后点一下记录。',
    '做得好！还可以从另外两项里，选一件容易做到的事。',
    '再记录一项，今天的三件小事就都完成啦；也可以按自己的节奏来。',
    '今天的努力已记下，明天也可以从一小步开始。',
  ];
  return {
    doneCount, percent: Math.round(doneCount / 3 * 100), weekDays, weekTrail,
    title: titles[doneCount], message: messages[doneCount], lastAction,
  };
}
function storageKey() {
  const profile = wx.getStorageSync('profile') || {};
  return `checkin_records_${profile.id || 'guest'}`;
}
module.exports = { dayKey, summarize, positiveFeedback, storageKey };
