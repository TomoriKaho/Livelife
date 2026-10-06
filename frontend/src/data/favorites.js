import { computed, ref } from 'vue';
import { activities } from './activities.js';

// 与日历的固定演示日期一致，让三个栏目都有可查看的示例。
export const DEMO_NOW = '2026-10-03T15:00:00+08:00';
export const favoriteTabs = [
  { id: 'upcoming', label: '待开始', pencil: 'blue' },
  { id: 'ongoing', label: '进行中', pencil: 'mint' },
  { id: 'ended', label: '已结束', pencil: 'lavender' },
];
export function activityStatus(activity, now = DEMO_NOW) {
  const time = new Date(now).getTime();
  const start = new Date(`${activity.date}T${activity.start}:00+08:00`).getTime();
  const end = new Date(`${activity.date}T${activity.end}:00+08:00`).getTime();
  return time < start ? 'upcoming' : time < end ? 'ongoing' : 'ended';
}
export const saved = ref(new Set(['film', 'reading', 'salon', 'ai', 'math', 'oct02-seminar']));
export const savedActivities = computed(() => activities.filter(item => saved.value.has(item.id)));
export function toggleSave(id) {
  if (!activities.some(item => item.id === id)) return;
  const next = new Set(saved.value);
  if (next.has(id)) next.delete(id);
  else next.add(id);
  saved.value = next;
}
export function removeSaved(id) {
  const next = new Set(saved.value);
  next.delete(id);
  saved.value = next;
}
export const activityMapRoute = item => ({ path: '/map', query: { activity: item.id } });
export const activityDetailRoute = item => ({ path: '/detail', query: { id: item.id } });
