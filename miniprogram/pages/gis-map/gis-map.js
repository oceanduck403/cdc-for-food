// pages/gis-map/gis-map.js
const { request } = require('../../utils/request.js');
const config = require('../../utils/config.js');
const mock = require('../../utils/mock.js');

Page({
  data: {
    latitude: config.gisCenter.latitude,
    longitude: config.gisCenter.longitude,
    markers: [],
    selected: null
  },

  onShow() {
    this.loadMarkers();
  },

  loadMarkers() {
    request({ url: '/gis/mushroom-risk?city=chengdu', showLoading: false })
      .then((data) => this.applyMarkers(data && data.items ? data.items : mock.mushroomMarkers.items))
      .catch(() => this.applyMarkers(mock.mushroomMarkers.items));
  },

  applyMarkers(items) {
    const markers = (items || []).map((m) => ({
      id: m.id,
      latitude: m.lat,
      longitude: m.lng,
      title: m.name,
      iconPath: '',
      width: 32,
      height: 32,
      callout: {
        content: `${m.name}\n${m.level} · ${m.period}`,
        color: '#FFFFFF',
        fontSize: 12,
        borderRadius: 6,
        bgColor: '#0F8A65',
        padding: 6,
        display: 'BYCLICK'
      }
    }));
    this.setData({ markers });
  },

  onMarkerTap(e) {
    const id = e.detail.markerId;
    const m = (this.data.markers || []).find((x) => x.id === id);
    if (!m) return;
    request({ url: `/gis/mushroom-risk/${id}`, showLoading: false })
      .then((detail) => this.setData({ selected: detail || this.fallbackDetail(m) }))
      .catch(() => this.setData({ selected: this.fallbackDetail(m) }));
  },

  fallbackDetail(m) {
    return {
      id: m.id,
      name: m.title,
      species: '—',
      level: m.callout ? m.callout.content.split('\n')[1].split(' · ')[0] : '—',
      period: m.callout ? m.callout.content.split('\n')[1].split(' · ')[1] : '',
      description: '该点位周边历史上发生过误采误食事件，请勿采摘野生菌。'
    };
  }
});
