const community = require('../../utils/community.js');
const navigation = require('../../utils/navigation.js');
Component({
  data: { count: 0, badge: '' },
  lifetimes: { detached() { this._visible=false; clearInterval(this._poll); } },
  pageLifetimes: {
    show() { this._visible=true; this.refresh(); clearInterval(this._poll); this._poll=setInterval(()=>this.refresh(),30000); },
    hide() { this._visible=false; clearInterval(this._poll); },
  },
  methods: {
    async refresh() {
      if(!community.loggedIn()) { this._token=''; this.setData({count:0,badge:''}); return; }
      const token=wx.getStorageSync('token');
      if(this._token !== token) { this._token=token; this.setData({count:0,badge:''}); }
      try { const data=await community.unread(); if(this._visible && token===wx.getStorageSync('token')) this.setData({count:data.count,badge:data.count>99?'99+':String(data.count)}); }
      catch { if(this._visible && token===wx.getStorageSync('token')) this.setData({count:0,badge:''}); }
    },
    messages() { if(community.requireLogin()) navigation.open('/pages/messages/messages'); },
    favorites() { if(community.requireLogin()) navigation.open('/pages/favorites/favorites'); },
  },
});
