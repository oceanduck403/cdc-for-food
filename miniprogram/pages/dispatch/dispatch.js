const api = require('../../utils/appointments.js');
Page({
  data: { appointments: [], doctors: [], onlineDoctors: [], pickerDoctors: [], waiting: 0, assigned: 0, loading: true, busy: false, error: '', updated: '' },
  onShow() {
    this._visible = true;
    this.refresh();
    clearInterval(this._timer);
    this._timer = setInterval(() => this.refresh(), 5000);
  },
  onHide() { this._visible = false; clearInterval(this._timer); },
  onUnload() { this.onHide(); },
  onPullDownRefresh() { this.refresh().finally(() => wx.stopPullDownRefresh()); },
  async refresh() {
    if (this._refreshing || this.data.busy) return;
    this._refreshing = true;
    try {
      const data = await api.dispatch();
      if (!this._visible) return;
      this.setData({ ...data, onlineDoctors: data.doctors.filter(d => d.online),
        waiting: data.appointments.filter(a => a.status === 'waiting').length,
        assigned: data.appointments.filter(a => a.status === 'assigned').length,
        loading: false, error: '', updated: new Date().toLocaleTimeString() });
    } catch (err) { this.setData({ loading: false, error: err.message }); }
    finally { this._refreshing = false; }
  },
  async mutate(action) {
    if (this.data.busy) return;
    this.setData({ busy: true });
    try { await action(); }
    catch (err) { wx.showToast({ title: err.message || '操作失败', icon: 'none' }); }
    finally { this.setData({ busy: false }); await this.refresh(); }
  },
  prepareDoctors() {
    this._picking = true;
    this.setData({ pickerDoctors: this.data.onlineDoctors.slice() });
  },
  chooseDoctor(e) {
    const doctor = this.data.pickerDoctors[Number(e.detail.value)];
    this._picking = false;
    if (doctor) this.mutate(() => api.adjust(e.currentTarget.dataset.id, 'assign', doctor.id));
  },
  changeStatus(e) {
    const { id, action } = e.currentTarget.dataset;
    wx.showModal({ title: action === 'complete' ? '结束本次服务' : '重新排队',
      content: action === 'complete' ? '结束后保留聊天记录，患者可再次预约。' : '关闭当前会话并重新等待匹配在线医生。',
      success: res => { if (res.confirm) this.mutate(() => api.adjust(id, action)); } });
  },
  toggleDoctor(e) {
    const { id, available } = e.currentTarget.dataset;
    this.mutate(() => api.availability(id, !available));
  },
});
