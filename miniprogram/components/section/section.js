Component({
  properties: {
    title: { type: String, value: '' },
    moreText: { type: String, value: '' }
  },
  methods: {
    onMore() { this.triggerEvent('more'); }
  }
});