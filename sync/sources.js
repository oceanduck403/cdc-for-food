// 公众号 RSS 源配置（今天看啥提供）
// 获取方式：
// 1. 打开 https://www.jintiankansha.com
// 2. 搜索公众号名称
// 3. 复制 RSS 订阅地址

export const SOURCES = [
  {
    id: 'cdcgz',
    name: '广东疾控',
    category: 'disease',
    rss: 'https://www.jintiankansha.com/column/S00001I1kW?rss=1',
    description: '广东省疾病预防控制中心官方公众号'
  },
  {
    id: 'chinacdc',
    name: '中国疾控中心',
    category: 'disease',
    rss: 'https://www.jintiankansha.com/column/mhJRaZImmS?rss=1',
    description: '中国疾病预防控制中心官方公众号'
  },
  {
    id: 'nutrition',
    name: '营养与健康',
    category: 'guide',
    rss: 'https://www.jintiankansha.com/column/HkQiEfJ9qO?rss=1',
    description: '中国疾控中心营养与健康所公众号'
  },
  {
    id: 'haoyingyang',
    name: '中国好营养',
    category: 'guide',
    rss: 'https://www.jintiankansha.com/column/v00023F5rX?rss=1',
    description: '中国营养学会科普公众号'
  },
  {
    id: 'yyclub',
    name: '中国营养界',
    category: 'guide',
    rss: 'https://www.jintiankansha.com/column/c00006E8Xz?rss=1',
    description: '中国营养学会官方公众号'
  }
];

// 分类标签颜色（与小程序保持一致）
export const TAG_COLORS = {
  guide:    { bg: '#E8F5F0', text: '#0F8A65' },
  mushroom: { bg: '#FEE2E2', text: '#EF4444' },
  safety:   { bg: '#FEF3C7', text: '#B45309' },
  disease:  { bg: '#EDE9FE', text: '#7C3AED' }
};
