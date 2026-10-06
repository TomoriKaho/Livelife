import { activities, calendarFilters, categories as sharedCategories } from '../../data/activities.js';

// 原型固定在参考稿的这一周，避免预览时“今天”跑到没有样例活动的日期。
export const TODAY = '2026-10-03';

export const HOURS = [8, 10, 12, 14, 16, 18, 20, 22];

export const categories = sharedCategories;
export const filters = calendarFilters;
export const events = activities;

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

function isCalendarEvent(item) {
  return item.category !== 'course';
}

function matchesCategory(item, category) {
  return isCalendarEvent(item) && (!category || category === 'all' || item.category === category);
}

export function eventsOn(dateKey, category = 'all') {
  return events
    .filter((item) => item.date === dateKey && matchesCategory(item, category))
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
  const category = categories[event.category];
  return category && { ...category, icon: category.calendarIcon };
}

export function marksOn(dateKey, category = 'all') {
  const seen = new Set();
  return eventsOn(dateKey, category)
    .map((item) => categoryOf(item))
    .filter((item) => item && !seen.has(item.id) && seen.add(item.id));
}

export function chipAt(dateKey, hour, category = 'all') {
  return eventsOn(dateKey, category).find((item) => slotOf(item.start) === hour);
}
