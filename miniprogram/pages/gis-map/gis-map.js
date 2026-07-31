// pages/gis-map/gis-map.js
const { request } = require('../../utils/request.js');
const config = require('../../utils/config.js');

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
      .then((data) => {
        const markers = (data.items || []).map((m) => ({
          id: m.id,
          latitude: m.lat,
          longitude: m.lng,
          title: m.name,
          iconPath: '/images/marker-mushroom.png',
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
      })
      .catch(() => {});
  },

  onMarkerTap(e) {
    const id = e.detail.markerId;
    const m = this.data.markers.find((x) => x.id === id);
    if (!m) return;
    request({ url: `/gis/mushroom-risk/${id}`, showLoading: false })
      .then((detail) => this.setData({ selected: detail }))
      .catch(() => {});
  }
});