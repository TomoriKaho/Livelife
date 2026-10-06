export const tags = [
  { id: 'ai', label: '人工智能', group: 'tech', pencil: 'blue' },
  { id: 'agent', label: 'AI Agent', group: 'tech', pencil: 'lavender' },
  { id: 'run', label: '跑步', group: 'sport', pencil: 'mint' },
  { id: 'ball', label: '篮球', group: 'sport', pencil: 'yellow' },
  { id: 'frontier', label: '科技前沿', group: 'tech', pencil: 'pink' },
  { id: 'lecture', label: '学术讲座', group: 'campus', pencil: 'mint' },
  { id: 'film', label: '电影放映', group: 'campus', pencil: 'pink' },
  { id: 'music', label: '音乐演出', group: 'campus', pencil: 'lavender' },
];

export const platforms = [
  { id: 'wechat', label: '公众号', mark: 'wechat', pencil: 'mint' },
  { id: 'zhihu', label: '知乎', mark: 'zhihu', pencil: 'blue' },
  { id: 'xhs', label: '小红书', mark: 'xhs', pencil: 'pink' },
  { id: 'google', label: 'Google', mark: 'google', pencil: 'yellow' },
  { id: 'official', label: '官网', mark: 'official', pencil: 'lavender' },
];

export const customPencils = ['blue', 'lavender', 'mint', 'yellow', 'pink'];

export const initialTagIds = ['ai', 'agent', 'run', 'ball', 'frontier'];

export const feedItems = [
  {
    id: 'ai-weekly',
    platform: 'wechat',
    title: '一周 AI 前沿速读：多模态与智能体',
    meta: '12分钟前 · 8分钟阅读',
    reason: '因为你关注',
    highlight: '人工智能',
    tag: 'ai',
    art: 'robot',
    saved: false,
  },
  {
    id: 'agent-howto',
    platform: 'zhihu',
    title: '普通人如何理解 AI Agent 的工作方式？',
    meta: '2小时前 · 326个回答',
    reason: '与你的',
    highlight: 'AI Agent',
    suffix: '标签相关',
    tag: 'agent',
    art: 'idea',
    saved: false,
  },
  {
    id: 'yanyuan-run',
    platform: 'xhs',
    title: '燕园 5 公里轻松跑路线分享',
    meta: '今天 · 1.2万次浏览',
    reason: '因为你喜欢',
    highlight: '跑步',
    tag: 'run',
    art: 'run',
    saved: false,
  },
  {
    id: 'ai-science',
    platform: 'google',
    title: 'AI for Science 最新研究合集',
    meta: '昨天 · 14 篇精选',
    reason: '因为你关注',
    highlight: '科技前沿',
    tag: 'frontier',
    art: 'science',
    saved: false,
  },
  {
    id: 'pku-ai-class',
    platform: 'wechat',
    title: '从课堂到实验室：北大 AI 公开课笔记',
    meta: '3小时前 · 6分钟阅读',
    reason: '因为你关注',
    highlight: '人工智能',
    tag: 'ai',
    art: 'robot',
    saved: false,
  },
  {
    id: 'ball-shoes',
    platform: 'zhihu',
    title: '五四球场夜场，碳板鞋到底要不要入？',
    meta: '5小时前 · 89个回答',
    reason: '因为你喜欢',
    highlight: '篮球',
    tag: 'ball',
    art: 'hoop',
    saved: false,
  },
  {
    id: 'weiming-run',
    platform: 'xhs',
    title: '未名湖晨跑打卡：秋天的第一口冷空气',
    meta: '昨天 · 8600次浏览',
    reason: '因为你喜欢',
    highlight: '跑步',
    tag: 'run',
    art: 'run',
    saved: false,
  },
  {
    id: 'multi-agent',
    platform: 'google',
    title: '多智能体协作近期综述与开源清单',
    meta: '昨天 · 9 篇精选',
    reason: '与你的',
    highlight: 'AI Agent',
    suffix: '标签相关',
    tag: 'agent',
    art: 'science',
    saved: false,
  },
  {
    id: 'embodied',
    platform: 'wechat',
    title: '科技前沿一周：具身智能与开源模型',
    meta: '今天 · 5分钟阅读',
    reason: '因为你关注',
    highlight: '科技前沿',
    tag: 'frontier',
    art: 'lab',
    saved: false,
  },
  {
    id: 'agent-start',
    platform: 'zhihu',
    title: '第一次接触 AI Agent，我是这样入门的',
    meta: '4小时前 · 210个回答',
    reason: '与你的',
    highlight: 'AI Agent',
    suffix: '标签相关',
    tag: 'agent',
    art: 'idea',
    saved: false,
  },
  {
    id: 'night-hoop',
    platform: 'xhs',
    title: '五四篮球场夜场攻略：人少、灯亮、好约球',
    meta: '今天 · 5400次浏览',
    reason: '因为你喜欢',
    highlight: '篮球',
    tag: 'ball',
    art: 'hoop',
    saved: false,
  },
  {
    id: 'conf-papers',
    platform: 'google',
    title: '2026 人工智能顶会论文速览',
    meta: '2天前 · 22 篇精选',
    reason: '因为你关注',
    highlight: '人工智能',
    tag: 'ai',
    art: 'science',
    saved: false,
  },
  {
    id: 'pku-festival',
    platform: 'official',
    title: '燕园秋季讲座周预告：从智能体到校园生活',
    meta: '今天 · 官网通知',
    reason: '因为你关注',
    highlight: '科技前沿',
    tag: 'frontier',
    art: 'lab',
    saved: false,
  },
  {
    id: 'ai-openday',
    platform: 'official',
    title: '人工智能研究院开放日报名开始',
    meta: '昨天 · 官网通知',
    reason: '因为你关注',
    highlight: '人工智能',
    tag: 'ai',
    art: 'science',
    saved: false,
  },
];

const summaries = {
  'tech+sport': '偏爱科技前沿，也喜欢保持活力',
  'tech+campus': '爱看学术与演出，也紧跟科技前沿',
  'sport+campus': '球场和剧场都想去，校园生活很满',
  tech: '最近更想靠近科技与智能体',
  sport: '最近更想动一动，把活力留下来',
  campus: '讲座、电影和演出，都想去看看',
  mixed: '兴趣很宽，想从全网慢慢遇见',
  empty: '还没圈定兴趣，先随便逛逛也可以',
};

export function portraitText(selectedIds, extraTags = []) {
  const catalog = [...tags, ...extraTags];
  const chosen = catalog.filter((item) => selectedIds.includes(item.id));
  const groups = new Set(chosen.map((item) => item.group).filter((group) => group !== 'custom'));
  if (!chosen.length) return summaries.empty;
  const has = (name) => groups.has(name);
  if (has('tech') && has('sport') && has('campus')) return summaries.mixed;
  if (has('tech') && has('sport')) return summaries['tech+sport'];
  if (has('tech') && has('campus')) return summaries['tech+campus'];
  if (has('sport') && has('campus')) return summaries['sport+campus'];
  if (has('tech')) return summaries.tech;
  if (has('sport')) return summaries.sport;
  if (has('campus')) return summaries.campus;
  const labels = chosen.slice(0, 2).map((item) => item.label).join('、');
  return labels ? `最近想看看「${labels}」` : summaries.mixed;
}

export function platformOf(id) {
  return platforms.find((item) => item.id === id);
}
