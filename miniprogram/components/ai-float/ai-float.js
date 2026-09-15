const WIDTH = 88;
const HEIGHT = 92;
const MARGIN = 16;
const BOTTOM_CLEARANCE = 110;
const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

Component({
  data: { visible: true, x: 0, y: 220, dragging: false },
  lifetimes: { attached() { this.layout(); } },
  pageLifetimes: {
    show() { this.setData({ visible: true }); this.layout(); },
    hide() { this.setData({ visible: false }); },
    resize() { this.layout(); },
  },
  methods: {
    layout() {
      const info = wx.getWindowInfo ? wx.getWindowInfo() : wx.getSystemInfoSync();
      this._width = info.windowWidth;
      this._height = info.windowHeight;
      const saved = wx.getStorageSync('floating_ai_position') || {};
      const maxX = Math.max(MARGIN, this._width - WIDTH - MARGIN);
      const maxY = Math.max(MARGIN, this._height - HEIGHT - BOTTOM_CLEARANCE);
      this.setData({
        x: saved.side === 'left' ? MARGIN : maxX,
        y: clamp(typeof saved.ratio === 'number' ? saved.ratio * this._height : maxY, MARGIN, maxY),
      });
    },
    touchStart(e) {
      if (!e.touches || !e.touches.length) return;
      const touch = e.touches[0];
      this._touch = { x: touch.clientX, y: touch.clientY, left: this.data.x, top: this.data.y };
      this._moved = false;
    },
    touchMove(e) {
      if (!this._touch || !e.touches || !e.touches.length) return;
      const touch = e.touches[0];
      const dx = touch.clientX - this._touch.x;
      const dy = touch.clientY - this._touch.y;
      if (Math.abs(dx) + Math.abs(dy) > 8) this._moved = true;
      if (!this._moved) return;
      const maxX = Math.max(MARGIN, this._width - WIDTH - MARGIN);
      const maxY = Math.max(MARGIN, this._height - HEIGHT - BOTTOM_CLEARANCE);
      this.setData({ dragging: true, x: clamp(this._touch.left + dx, MARGIN, maxX), y: clamp(this._touch.top + dy, MARGIN, maxY) });
    },
    touchEnd() {
      if (this._moved) {
        this._ignoreTapUntil = Date.now() + 400;
        const side = this.data.x + WIDTH / 2 < this._width / 2 ? 'left' : 'right';
        const x = side === 'left' ? MARGIN : Math.max(MARGIN, this._width - WIDTH - MARGIN);
        this.setData({ x, dragging: false });
        wx.setStorageSync('floating_ai_position', { side, ratio: this.data.y / this._height });
      } else if (this._touch) {
        // Some WeChat versions swallow bindtap after catchtouchend; open here as well.
        this.openAiPage();
      }
      this._touch = null;
    },
    touchCancel() { this._moved = true; this.touchEnd(); },
    openAiPage() {
      if (Date.now() < (this._ignoreTapUntil || 0)) return;
      if (Date.now() - (this._lastOpen || 0) < 700) return;
      this._lastOpen = Date.now();
      wx.navigateTo({
        url: '/pages/consult-ai/consult-ai',
        fail: err => {
          if (/limit|层级|page stack/i.test(err.errMsg || '') && wx.redirectTo) {
            wx.redirectTo({ url: '/pages/consult-ai/consult-ai' });
          } else wx.showToast({ title: 'AI 咨询暂时无法打开，请重新编译后再试', icon: 'none' });
        },
      });
    },
  },
});
