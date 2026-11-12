import { computed, onBeforeUnmount, ref, watch, type Ref } from 'vue';
import { fetchCalendarActivities, type CalendarActivity } from '../../api/map-activities';

const date = new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Shanghai' });
const clock = new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Shanghai', hour: '2-digit', minute: '2-digit' });
const styles = [
  { pencil: 'pink', icon: 'speaker' }, { pencil: 'mint', icon: 'music' }, { pencil: 'lavender', icon: 'people' },
];
export function calendarEvent(item: CalendarActivity) {
  return { ...item, date: date.format(new Date(item.start_at)), start: clock.format(new Date(item.start_at)),
    end: item.end_at ? clock.format(new Date(item.end_at)) : null, place: item.location,
    chip: item.title || '活动', category: item.platform };
}
type Event = ReturnType<typeof calendarEvent>;
export function useCalendarActivities(start: Ref<string>, end: Ref<string>) {
  const events = ref<Event[]>([]), loading = ref(false), error = ref('');
  let controller: AbortController | null = null, generation = 0;
  const publishers = computed(() => [...new Map(events.value.map(e => [e.platform, e.source_name || e.platform])).entries()]
    .sort(([a], [b]) => a.localeCompare(b)).map(([id, label], i) => ({ id, label: label.replace(/^北京大学/, ''), ...styles[i % styles.length] })));
  const filters = computed(() => [{ id: 'all', label: '全部', pencil: 'yellow', icon: 'people' }, ...publishers.value]);
  const categoryOf = (event: Event) => publishers.value.find(p => p.id === event.platform) || filters.value[0];
  const eventsOn = (key: string, category = 'all') => events.value.filter(e => e.date === key && (category === 'all' || e.platform === category));
  const marksOn = (key: string, category = 'all') => [...new Map(eventsOn(key, category).map(e => [e.platform, categoryOf(e)])).values()];
  const chipAt = (key: string, hour: number, category = 'all') => eventsOn(key, category).filter(e => Math.min(20, Math.max(8, Math.round(Number(e.start.slice(0, 2)) / 2) * 2)) === hour);
  async function reload() {
    const current = ++generation;
    controller?.abort();
    const active = new AbortController(); controller = active;
    events.value = []; error.value = ''; loading.value = true;
    const timeout = setTimeout(() => active.abort(), 10_000);
    try {
      const result = await fetchCalendarActivities(`${start.value}T00:00:00+08:00`, `${end.value}T00:00:00+08:00`, active.signal);
      if (current === generation) events.value = result.items.map(calendarEvent);
    } catch (cause) {
      if (current === generation) error.value = active.signal.aborted ? '活动读取超时，请重试。' : cause instanceof Error ? cause.message : '活动读取失败。';
    } finally {
      clearTimeout(timeout);
      if (current === generation) loading.value = false;
    }
  }
  watch([start, end], reload, { immediate: true });
  onBeforeUnmount(() => { generation++; controller?.abort(); });
  return { events, loading, error, reload, filters, categoryOf, eventsOn, marksOn, chipAt };
}
