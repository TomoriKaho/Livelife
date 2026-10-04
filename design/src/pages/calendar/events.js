// 原型固定在参考稿的这一周，避免预览时“今天”跑到没有样例活动的日期。
export const TODAY = '2026-10-03';

export const HOURS = [8, 10, 12, 14, 16, 18, 20, 22];

export const categories = {
  lecture: { id: 'lecture', label: '讲座', pencil: 'pink', mark: '#e88880', icon: 'speaker' },
  film: { id: 'film', label: '电影', pencil: 'yellow', mark: '#f0b24a', icon: 'music' },
  club: { id: 'club', label: '学生活动', pencil: 'blue', mark: '#6aaee8', icon: 'people' },
};

export const legend = [categories.lecture, categories.film, categories.club];

export const events = [
  { id: 'oct02-seminar', title: '数据结构答疑课', chip: '答疑', category: 'club', date: '2026-10-02', start: '16:00', end: '17:30', place: '理科教学楼103' },
  { id: 'oct03-ai', title: '大模型与智能体讲座', chip: 'AI讲座', category: 'lecture', date: '2026-10-03', start: '14:00', end: '15:30', place: '理科教学楼208' },
  { id: 'oct03-photo', title: '校园摄影工作坊', chip: '摄影', category: 'club', date: '2026-10-03', start: '16:00', end: '17:30', place: '新太阳活动中心' },
  { id: 'oct03-film', title: '悬疑电影放映', chip: '电影', category: 'film', date: '2026-10-03', start: '19:00', end: '21:30', place: '百周年纪念讲堂' },
  { id: 'oct04-club', title: '学生会例会', chip: '社团', category: 'club', date: '2026-10-04', start: '10:00', end: '11:30', place: '新太阳活动中心' },
  { id: 'oct04-volunteer', title: '志愿讲解培训', chip: '志愿', category: 'club', date: '2026-10-04', start: '14:00', end: '15:30', place: '校史馆' },
  { id: 'oct04-dance', title: '舞蹈社排练', chip: '社团', category: 'club', date: '2026-10-04', start: '16:00', end: '18:00', place: '五四体育馆' },
  { id: 'oct05-innovate', title: '创新创业讲座', chip: '创新讲座', category: 'lecture', date: '2026-10-05', start: '10:00', end: '11:30', place: '理科教学楼207' },
  { id: 'oct06-photo', title: '夜拍校园活动', chip: '摄影', category: 'club', date: '2026-10-06', start: '10:00', end: '12:00', place: '未名湖' },
  { id: 'oct06-volunteer', title: '图书馆志愿整理', chip: '志愿', category: 'club', date: '2026-10-06', start: '14:00', end: '16:00', place: '图书馆' },
  { id: 'oct06-film', title: '经典电影放映', chip: '电影', category: 'film', date: '2026-10-06', start: '18:00', end: '20:30', place: '百周年纪念讲堂' },
  { id: 'oct07-film', title: '纪录片放映', chip: '电影', category: 'film', date: '2026-10-07', start: '10:00', end: '12:00', place: '二教107' },
  { id: 'oct07-drama', title: '话剧社排练', chip: '社团', category: 'club', date: '2026-10-07', start: '16:00', end: '18:00', place: '百年讲堂排练厅' },
  { id: 'oct08-humanities', title: '人文经典讲座', chip: '人文讲座', category: 'lecture', date: '2026-10-08', start: '14:00', end: '15:30', place: '人文楼报告厅' },
  { id: 'oct08-outdoor', title: '未名湖露天电影', chip: '露天电影', category: 'film', date: '2026-10-08', start: '20:00', end: '22:00', place: '未名湖畔' },
  { id: 'oct09-volunteer', title: '迎新志愿活动', chip: '志愿', category: 'club', date: '2026-10-09', start: '10:00', end: '12:00', place: '正大国际中心' },
  { id: 'oct09-photo', title: '摄影社外拍', chip: '摄影', category: 'club', date: '2026-10-09', start: '16:00', end: '18:00', place: '燕南园' },
  { id: 'oct10-lecture', title: '心理学公开课', chip: '讲座', category: 'lecture', date: '2026-10-10', start: '14:00', end: '15:30', place: '二教101' },
  { id: 'oct10-film', title: '动画电影夜', chip: '电影', category: 'film', date: '2026-10-10', start: '19:00', end: '21:00', place: '百周年纪念讲堂' },
  { id: 'oct11-film', title: '小剧场放映', chip: '电影', category: 'film', date: '2026-10-11', start: '19:00', end: '21:00', place: '艺园' },
  { id: 'oct14-club', title: '篮球友谊赛', chip: '社团', category: 'club', date: '2026-10-14', start: '16:00', end: '18:00', place: '五四体育馆' },
  { id: 'oct17-film', title: '法语电影周', chip: '电影', category: 'film', date: '2026-10-17', start: '19:00', end: '21:00', place: '百周年纪念讲堂' },
  { id: 'oct22-club', title: '合唱团排练', chip: '社团', category: 'club', date: '2026-10-22', start: '18:00', end: '20:00', place: '百年讲堂排练厅' },
  { id: 'oct26-lecture', title: '科学前沿讲座', chip: '讲座', category: 'lecture', date: '2026-10-26', start: '14:00', end: '15:30', place: '理科教学楼201' },
  { id: 'oct26-club', title: '社团招新复试', chip: '社团', category: 'club', date: '2026-10-26', start: '16:00', end: '18:00', place: '新太阳活动中心' },
  { id: 'oct29-film', title: '午夜场电影', chip: '电影', category: 'film', date: '2026-10-29', start: '20:00', end: '22:00', place: '百周年纪念讲堂' },
];

const weekdayShort = ['日', '一', '二', '三', '四', '五', '六'];
const weekdayFull = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六'];

export function parseKey(key) {
  const [year, month, day] = key.split('-').map(Number);
  return new Date(year, month - 1, day);
}

export function toKey(date) {
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${date.getFullYear()}-${month}-${day}`;
}

export function addDays(date, count) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate() + count);
}

export function startOfMondayWeek(date) {
  const offset = date.getDay() === 0 ? -6 : 1 - date.getDay();
  return addDays(date, offset);
}

export function daysFrom(start, count = 7) {
  return Array.from({ length: count }, (_, index) => addDays(start, index));
}

export function monthCells(year, month) {
  const start = startOfMondayWeek(new Date(year, month, 1));
  const cells = daysFrom(start, 42).map((date) => ({
    key: toKey(date),
    day: date.getDate(),
    inMonth: date.getMonth() === month,
  }));
  return cells[35].inMonth ? cells : cells.slice(0, 35);
}

export function weekdayLabel(date, full = false) {
  return (full ? weekdayFull : weekdayShort)[date.getDay()];
}

export function formatMonth(year, month) {
  return `${year}年${month + 1}月`;
}

export function formatDay(date, { today = false } = {}) {
  const head = `${date.getMonth() + 1}月${date.getDate()}日`;
  return today ? `${head} · 今天` : `${head} · ${weekdayLabel(date, true)}`;
}

export function formatRange(start, end) {
  return `${start.getMonth() + 1}月${start.getDate()}日 - ${end.getMonth() + 1}月${end.getDate()}日`;
}

export function slotOf(start) {
  const hour = Number(start.slice(0, 2));
  return Math.min(20, Math.max(8, Math.round(hour / 2) * 2));
}

export function eventsOn(dateKey) {
  return events
    .filter((item) => item.date === dateKey)
    .sort((a, b) => a.start.localeCompare(b.start));
}

export function eventsByDay(dateKeys) {
  const map = new Map(dateKeys.map((key) => [key, []]));
  for (const item of events) {
    map.get(item.date)?.push(item);
  }
  for (const list of map.values()) {
    list.sort((a, b) => a.start.localeCompare(b.start));
  }
  return map;
}

export function categoryOf(event) {
  return categories[event.category];
}

export function marksOn(dateKey) {
  const seen = new Set();
  return eventsOn(dateKey)
    .map((item) => categoryOf(item))
    .filter((item) => item && !seen.has(item.id) && seen.add(item.id));
}

export function chipAt(dateKey, hour) {
  return eventsOn(dateKey).find((item) => slotOf(item.start) === hour);
}
