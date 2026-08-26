// pages/gis-map/gis-map.js
const { request } = require('../../utils/request.js');
const config = require('../../utils/config.js');
const mock = require('../../utils/mock.js');

// 四川省近似边界框（用于粗略校验）
const SICHUAN_BOUNDS = {
  minLat: 26.0,   // 最南端
  maxLat: 34.3,   // 最北端
  minLng: 97.3,   // 最西端
  maxLng: 108.6   // 最东端
};

// 成都及周边风险区域（预设数据）
const PRESET_RISK_AREAS = [
  { id: 'pre-001', lat: 30.5640, lng: 104.2780, name: '龙泉山片区', species: '致命鹅膏', level: '高风险', period: '6-9月', description: '该区域历史上曾发生多起误采误食致命鹅膏中毒事件，请勿采摘任何野生菌。' },
  { id: 'pre-002', lat: 30.9050, lng: 103.5950, name: '青城山片区', species: '假褐云斑鹅膏', level: '中风险', period: '7-8月', description: '近年成都地区中毒事件的主要毒蘑菇种类之一。' },
  { id: 'pre-003', lat: 30.9870, lng: 103.9480, name: '彭州山区', species: '黄盖鹅膏', level: '高风险', period: '6-8月', description: '剧毒菌类集中分布区，建议避免进山采集。' },
  { id: 'pre-004', lat: 30.6520, lng: 103.4520, name: '都江堰山区', species: '未知毒菌', level: '中风险', period: '6-9月', description: '山区野生菌种类繁多，难以辨别，请勿采食。' },
  { id: 'pre-005', lat: 30.1560, lng: 102.8520, name: '大邑西岭雪山', species: '多种毒菌', level: '高风险', period: '7-10月', description: '高海拔地区蘑菇生长季节长，中毒风险高。' },
];

// 尝试从本地存储获取用户标记
function getUserMarkers() {
  try {
    const stored = wx.getStorageSync('userMarkers') || '[]';
    return JSON.parse(stored);
  } catch (e) {
    return [];
  }
}

// 保存用户标记到本地
function saveUserMarkers(markers) {
  try {
    wx.setStorageSync('userMarkers', JSON.stringify(markers));
  } catch (e) {
    console.error('保存标记失败', e);
  }
}

Page({
  data: {
    latitude: config.gisCenter.latitude,
    longitude: config.gisCenter.longitude,
    scale: 9,
    markers: [],
    presetMarkers: [],    // 系统预设标记
    userMarkers: [],     // 用户标记
    selected: null,
    markMode: false,     // 标记模式
    currentRegion: '全部区域',
    regions: ['全部区域', '成都市', '绵阳市', '德阳市', '雅安市', '阿坝州', '甘孜州', '凉山州'],
    showAddForm: false,
    newMarker: {
      name: '',
      species: '',
      level: '中风险',
      period: '',
      description: ''
    },
    showUserMarkers: true,  // 是否显示用户标记
    offlineMode: false,     // 离线模式标识
  },

  onLoad() {
    // 检查网络状态
    this.checkNetworkStatus();
  },

  onShow() {
    this.loadAllMarkers();
  },

  onUnload() {
    // 清理
  },

  // 检查网络状态
  checkNetworkStatus() {
    wx.getNetworkType({
      success: (res) => {
        const isOffline = res.networkType === 'none' || res.networkType === 'unknown';
        this.setData({ offlineMode: isOffline });
      }
    });
  },

  // 加载所有标记
  loadAllMarkers() {
    // 加载预设标记
    this.loadPresetMarkers();
    // 加载用户标记
    const userMarkers = getUserMarkers();
    this.setData({ userMarkers });
    this.mergeMarkers();
  },

  // 加载系统预设标记
  loadPresetMarkers() {
    request({ url: '/gis/mushroom-risk?city=chengdu', showLoading: false })
      .then((data) => {
        const items = data && data.items ? data.items : PRESET_RISK_AREAS;
        this.setData({ presetMarkers: items });
        this.mergeMarkers();
      })
      .catch(() => {
        // 使用本地预设数据
        this.setData({ presetMarkers: PRESET_RISK_AREAS });
        this.mergeMarkers();
      });
  },

  // 合并预设和用户标记
  mergeMarkers() {
    const presetMarkers = this.formatPresetMarkers(this.data.presetMarkers);
    const userMarkers = this.formatUserMarkers(this.data.userMarkers);
    
    let allMarkers = [...presetMarkers, ...userMarkers];
    
    // 按区域筛选
    if (this.data.currentRegion !== '全部区域') {
      allMarkers = allMarkers.filter(m => m.region === this.data.currentRegion);
    }
    
    // 如果不显示用户标记
    if (!this.data.showUserMarkers) {
      allMarkers = allMarkers.filter(m => !m.isUser);
    }
    
    this.setData({ markers: allMarkers });
  },

  // 格式化预设标记
  formatPresetMarkers(items) {
    return (items || []).map((m, idx) => ({
      id: m.id || `preset-${idx}`,
      latitude: m.lat || m.latitude,
      longitude: m.lng || m.longitude,
      title: m.name,
      width: 32,
      height: 40,
      isUser: false,
      region: m.region || this.getRegionFromCoords(m.lat || m.latitude, m.lng || m.longitude),
      callout: {
        content: `${m.name}\n${m.level || '中风险'} · ${m.period || '全年'}`,
        color: '#FFFFFF',
        fontSize: 12,
        borderRadius: 6,
        bgColor: this.getLevelColor(m.level),
        padding: 6,
        display: 'BYCLICK'
      },
      raw: m
    }));
  },

  // 格式化用户标记
  formatUserMarkers(items) {
    return (items || []).map((m, idx) => ({
      id: m.id || `user-${Date.now()}-${idx}`,
      latitude: m.lat,
      longitude: m.lng,
      title: m.name,
      width: 32,
      height: 40,
      isUser: true,
      region: m.region || this.getRegionFromCoords(m.lat, m.lng),
      callout: {
        content: `${m.name}\n${m.level || '中风险'} · ${m.period || '请填写'}`,
        color: '#FFFFFF',
        fontSize: 12,
        borderRadius: 6,
        bgColor: '#6B7280',
        padding: 6,
        display: 'BYCLICK'
      },
      raw: m
    }));
  },

  // 根据风险等级获取颜色
  getLevelColor(level) {
    const map = {
      '高风险': '#EF4444',
      '中风险': '#F59E0B',
      '低风险': '#10B981'
    };
    return map[level] || '#6B7280';
  },

  // 根据坐标判断所属区域（简化版）
  getRegionFromCoords(lat, lng) {
    // 成都区域
    if (lat >= 30.2 && lat <= 31.0 && lng >= 103.5 && lng <= 104.6) {
      return '成都市';
    }
    // 绵阳
    if (lat >= 31.0 && lat <= 32.0 && lng >= 104.0 && lng <= 105.5) {
      return '绵阳市';
    }
    // 德阳
    if (lat >= 30.8 && lat <= 31.5 && lng >= 104.0 && lng <= 104.8) {
      return '德阳市';
    }
    // 雅安
    if (lat >= 29.5 && lat <= 30.5 && lng >= 102.5 && lng <= 103.5) {
      return '雅安市';
    }
    // 阿坝
    if (lat >= 31.0 && lat <= 34.0 && lng >= 97.0 && lng <= 104.0) {
      return '阿坝州';
    }
    // 甘孜
    if (lat >= 28.0 && lat <= 33.0 && lng >= 98.0 && lng <= 102.5) {
      return '甘孜州';
    }
    // 凉山
    if (lat >= 26.0 && lat <= 29.0 && lng >= 100.5 && lng <= 103.5) {
      return '凉山州';
    }
    return '成都市';
  },

  // 点击标记
  onMarkerTap(e) {
    const id = e.detail.markerId;
    const marker = (this.data.markers || []).find(m => m.id === id);
    if (!marker) return;

    const detail = marker.isUser ? marker.raw : {
      id: marker.id,
      name: marker.title,
      species: marker.raw.species || '未知',
      level: marker.raw.level || '中风险',
      period: marker.raw.period || '未知',
      description: marker.raw.description || '暂无描述',
      isUser: false
    };

    // 用户标记添加更多信息
    if (marker.isUser) {
      detail.isUser = true;
      detail.createdAt = marker.raw.createdAt;
      detail.canDelete = true;
    }

    this.setData({ selected: detail });
  },

  // 点击地图（标记模式）
  onMapTap(e) {
    if (!this.data.markMode) return;
    
    const { latitude, longitude } = e.detail;
    
    // 检查是否在四川省范围内
    if (!this.isInSichuan(latitude, longitude)) {
      wx.showToast({
        title: '仅支持四川省内区域',
        icon: 'none'
      });
      return;
    }

    // 保存点击位置，打开添加表单
    this.setData({
      newMarker: {
        ...this.data.newMarker,
        lat: latitude,
        lng: longitude,
        name: '',
        species: '',
        level: '中风险',
        period: '',
        description: ''
      },
      showAddForm: true
    });
  },

  // 检查坐标是否在四川省内
  isInSichuan(lat, lng) {
    // 粗略边界检查
    if (lat < SICHUAN_BOUNDS.minLat || lat > SICHUAN_BOUNDS.maxLat) return false;
    if (lng < SICHUAN_BOUNDS.minLng || lng > SICHUAN_BOUNDS.maxLng) return false;
    return true;
  },

  // 切换标记模式
  toggleMarkMode() {
    const newMode = !this.data.markMode;
    this.setData({ markMode: newMode });
    
    if (newMode) {
      wx.showModal({
        title: '标记模式',
        content: '点击地图上的位置即可添加标记点。请确保位置在四川省内。',
        showCancel: false
      });
    }
  },

  // 切换区域
  onRegionChange(e) {
    const index = e.detail.value;
    const region = this.data.regions[index];
    this.setData({ currentRegion: region });
    this.mergeMarkers();
  },

  // 切换用户标记显示
  toggleUserMarkers() {
    this.setData({ showUserMarkers: !this.data.showUserMarkers });
    this.mergeMarkers();
  },

  // 打开添加表单
  openAddForm() {
    this.setData({ showAddForm: true });
  },

  // 关闭添加表单
  closeAddForm() {
    this.setData({ 
      showAddForm: false,
      newMarker: {
        name: '',
        species: '',
        level: '中风险',
        period: '',
        description: ''
      }
    });
  },

  // 更新表单字段
  onFormInput(e) {
    const field = e.currentTarget.dataset.field;
    const value = e.detail.value;
    this.setData({
      newMarker: {
        ...this.data.newMarker,
        [field]: value
      }
    });
  },

  // 选择风险等级
  onLevelChange(e) {
    const levels = ['高风险', '中风险', '低风险'];
    const index = parseInt(e.detail.value);
    this.setData({
      newMarker: {
        ...this.data.newMarker,
        level: levels[index]
      }
    });
  },

  // 保存新标记
  saveMarker() {
    const { newMarker } = this.data;
    
    if (!newMarker.name || !newMarker.name.trim()) {
      wx.showToast({ title: '请填写标记名称', icon: 'none' });
      return;
    }

    // 验证坐标
    if (!newMarker.lat || !newMarker.lng) {
      wx.showToast({ title: '请先在地图上选择位置', icon: 'none' });
      return;
    }

    // 检查是否在四川省内
    if (!this.isInSichuan(newMarker.lat, newMarker.lng)) {
      wx.showToast({ title: '仅支持四川省内区域', icon: 'none' });
      return;
    }

    // 创建标记对象
    const marker = {
      id: `user-${Date.now()}`,
      lat: newMarker.lat,
      lng: newMarker.lng,
      name: newMarker.name.trim(),
      species: newMarker.species || '未知名',
      level: newMarker.level || '中风险',
      period: newMarker.period || '',
      description: newMarker.description || '',
      region: this.getRegionFromCoords(newMarker.lat, newMarker.lng),
      createdAt: new Date().toISOString().split('T')[0]
    };

    // 保存到本地
    const userMarkers = getUserMarkers();
    userMarkers.push(marker);
    saveUserMarkers(userMarkers);

    // 更新状态
    this.setData({
      userMarkers,
      showAddForm: false,
      markMode: false,
      newMarker: { name: '', species: '', level: '中风险', period: '', description: '' }
    });

    this.mergeMarkers();
    
    wx.showToast({ title: '标记已添加', icon: 'success' });
  },

  // 删除用户标记
  deleteMarker() {
    if (!this.data.selected || !this.data.selected.isUser) return;

    wx.showModal({
      title: '确认删除',
      content: `确定要删除标记「${this.data.selected.name}」吗？`,
      success: (res) => {
        if (res.confirm) {
          const userMarkers = getUserMarkers().filter(m => m.id !== this.data.selected.id);
          saveUserMarkers(userMarkers);
          
          this.setData({
            userMarkers,
            selected: null
          });
          
          this.mergeMarkers();
          wx.showToast({ title: '已删除', icon: 'success' });
        }
      }
    });
  },

  // 关闭详情弹窗
  closeDetail() {
    this.setData({ selected: null });
  },

  // 定位到当前位置
  locateToCurrent() {
    wx.getLocation({
      type: 'gcj02',
      success: (res) => {
        const { latitude, longitude } = res;
        
        // 检查是否在四川省内
        if (!this.isInSichuan(latitude, longitude)) {
          wx.showToast({
            title: '当前位置不在四川省内',
            icon: 'none'
          });
          // 仍然移动到该位置
          this.setData({
            latitude,
            longitude,
            scale: 13
          });
          return;
        }

        this.setData({
          latitude,
          longitude,
          scale: 13
        });
      },
      fail: () => {
        wx.showToast({
          title: '定位失败，请检查权限',
          icon: 'none'
        });
      }
    });
  },

  // 清除所有用户标记
  clearAllMarkers() {
    wx.showModal({
      title: '确认清除',
      content: '确定要清除所有用户标记吗？此操作不可恢复。',
      success: (res) => {
        if (res.confirm) {
          saveUserMarkers([]);
          this.setData({ userMarkers: [] });
          this.mergeMarkers();
          wx.showToast({ title: '已清除全部', icon: 'success' });
        }
      }
    });
  },

  // 导出标记数据
  exportMarkers() {
    const userMarkers = getUserMarkers();
    if (userMarkers.length === 0) {
      wx.showToast({ title: '暂无用户标记', icon: 'none' });
      return;
    }

    const content = JSON.stringify(userMarkers, null, 2);
    const fileName = `毒蘑菇标记_${new Date().toISOString().split('T')[0]}.json`;

    wx.getFileSystemManager().writeFile({
      filePath: `${wx.env.USER_DATA_PATH}/${fileName}`,
      data: content,
      success: () => {
        wx.showModal({
          title: '导出成功',
          content: `文件已保存至：${fileName}\n可在「发现」→「小程序」→「打开文件」中查看`,
          showCancel: false
        });
      },
      fail: () => {
        // 降级：复制到剪贴板
        wx.setClipboardData({
          data: content,
          success: () => {
            wx.showToast({ title: '已复制到剪贴板', icon: 'success' });
          }
        });
      }
    });
  }
});
