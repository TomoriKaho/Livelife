<script>
// 本页面的路由、标题与强调色在本文件维护，路由自动读取。
export const pageMeta = {
  "key": "calendar",
  "id": "D-04",
  "title": "活动日历",
  "placeholder": "按月、按周查看校园活动",
  "label": "CALENDAR",
  "eyebrow": "MAKE ROOM FOR GOOD DAYS",
  "icon": "calendar",
  "accent": "mint",
  "nav": "calendar",
  "back": false,
  "heading": false,
  "footer": false
};
</script>

<script setup>
import { computed, ref } from 'vue';
import { RouterLink } from 'vue-router';
import AppIcon from '../components/AppIcon.vue';
import CalendarIcon from './calendar/CalendarIcon.vue';
import PencilSwatch from './calendar/PencilSwatch.vue';
import {
  TODAY,
  HOURS,
  legend,
  addDays,
  categoryOf,
  chipAt,
  daysFrom,
  eventsOn,
  formatDay,
  formatMonth,
  formatRange,
  marksOn,
  monthCells,
  parseKey,
  toKey,
  weekdayLabel,
} from './calendar/events.js';

const views = [
  { id: 'month', label: '月' },
  { id: 'week', label: '周' },
];

const view = ref('month');
const selectedKey = ref(TODAY);
const monthCursor = ref(parseKey(TODAY));
const weekStart = ref(parseKey(TODAY));
const saved = ref(new Set());

const selectedDate = computed(() => parseKey(selectedKey.value));
const selectedEvents = computed(() => eventsOn(selectedKey.value));
const isTodaySelected = computed(() => selectedKey.value === TODAY);
const weekDays = computed(() => daysFrom(weekStart.value));
const weekKeys = computed(() => weekDays.value.map(toKey));
const weekSlots = computed(() => HOURS.map((hour) => ({
  hour,
  cells: weekKeys.value.map((key) => {
    const event = chipAt(key, hour);
    return event ? { key, event, category: categoryOf(event) } : { key, event: null };
  }),
})));
const monthGrid = computed(() => monthCells(monthCursor.value.getFullYear(), monthCursor.value.getMonth()));
const monthTitle = computed(() => formatMonth(monthCursor.value.getFullYear(), monthCursor.value.getMonth()));
const weekTitle = computed(() => formatRange(weekStart.value, addDays(weekStart.value, 6)));
const selectedTitle = computed(() => formatDay(selectedDate.value, { today: isTodaySelected.value }));
const weekdayHeads = ['一', '二', '三', '四', '五', '六', '日'];

function setView(next) {
  view.value = next;
  if (next === 'week') {
    const selected = selectedDate.value;
    const end = addDays(weekStart.value, 6);
    if (selected < weekStart.value || selected > end) weekStart.value = selected;
    return;
  }
  monthCursor.value = new Date(selectedDate.value.getFullYear(), selectedDate.value.getMonth(), 1);
}

function shift(step) {
  if (view.value === 'month') {
    monthCursor.value = new Date(monthCursor.value.getFullYear(), monthCursor.value.getMonth() + step, 1);
    return;
  }
  weekStart.value = addDays(weekStart.value, step * 7);
  const end = addDays(weekStart.value, 6);
  const selected = selectedDate.value;
  if (selected < weekStart.value || selected > end) selectedKey.value = toKey(weekStart.value);
}

function selectDay(key) {
  selectedKey.value = key;
}

function toggleSave(id) {
  const next = new Set(saved.value);
  if (next.has(id)) next.delete(id);
  else next.add(id);
  saved.value = next;
}

function marks(key) {
  return marksOn(key);
}

function dayPencil(key) {
  if (key === TODAY) return 'pink';
  if (key === selectedKey.value) return 'blue';
  return undefined;
}
</script>

<template>
  <section class="calendar-page" aria-labelledby="page-title">
    <div class="toolbar">
      <div class="title-block">
        <h1 id="page-title" tabindex="-1">活动日历</h1>
        <p class="lede">安排你的校园生活</p>
      </div>
      <div v-sketch class="view-switch sketch sketch-white" role="tablist" aria-label="月视图或周视图">
        <button
          v-for="item in views"
          :key="`${item.id}-${view === item.id}`"
          v-sketch
          class="view-tab"
          :class="view === item.id ? 'sketch pencil-fill sketch-fill-only' : ''"
          :data-pencil="view === item.id ? 'blue' : undefined"
          type="button"
          role="tab"
          :aria-selected="view === item.id"
          @click="setView(item.id)"
        >{{ item.label }}</button>
      </div>
    </div>

    <article v-sketch class="board sketch sketch-white">
      <div class="board-nav">
        <button class="nudge" type="button" :aria-label="view === 'month' ? '上个月' : '上一周'" @click="shift(-1)">
          <AppIcon class="nudge-icon is-left" name="chevron" />
        </button>
        <p class="board-title">{{ view === 'month' ? monthTitle : weekTitle }}</p>
        <button class="nudge" type="button" :aria-label="view === 'month' ? '下个月' : '下一周'" @click="shift(1)">
          <AppIcon class="nudge-icon" name="chevron" />
        </button>
      </div>

      <div v-if="view === 'month'" class="month" role="grid" aria-label="月历">
        <div class="month-head" role="row">
          <span v-for="label in weekdayHeads" :key="label" role="columnheader">{{ label }}</span>
        </div>
        <div class="month-body">
          <button
            v-for="cell in monthGrid"
            :key="cell.key"
            class="month-day"
            :class="{
              'is-out': !cell.inMonth,
              'is-today': cell.key === TODAY,
              'is-selected': cell.key === selectedKey,
            }"
            type="button"
            role="gridcell"
            :aria-current="cell.key === selectedKey ? 'date' : undefined"
            :aria-label="`${cell.key}${cell.key === TODAY ? ' 今天' : ''}`"
            @click="selectDay(cell.key)"
          >
            <span
              v-if="dayPencil(cell.key)"
              :key="`${cell.key}-${dayPencil(cell.key)}`"
              v-sketch
              class="day-num sketch pencil-fill sketch-fill-only"
              :data-pencil="dayPencil(cell.key)"
            >{{ cell.day }}</span>
            <span v-else class="day-num">{{ cell.day }}</span>
            <span class="dots" aria-hidden="true">
              <PencilSwatch v-for="item in marks(cell.key)" :key="item.id" :pencil="item.pencil" />
            </span>
          </button>
        </div>
      </div>

      <div v-else class="week" role="grid" aria-label="周日程">
        <div class="week-head">
          <span class="time-gutter" aria-hidden="true"></span>
          <button
            v-for="day in weekDays"
            :key="toKey(day)"
            class="week-day"
            :class="{ 'is-today': toKey(day) === TODAY, 'is-selected': toKey(day) === selectedKey }"
            type="button"
            @click="selectDay(toKey(day))"
          >
            <span class="week-label">{{ weekdayLabel(day) }}</span>
            <span
              v-if="dayPencil(toKey(day))"
              :key="`${toKey(day)}-${dayPencil(toKey(day))}`"
              v-sketch
              class="day-num sketch pencil-fill sketch-fill-only"
              :data-pencil="dayPencil(toKey(day))"
            >{{ day.getDate() }}</span>
            <span v-else class="day-num">{{ day.getDate() }}</span>
            <span v-if="toKey(day) === TODAY" class="today-tag">今天</span>
          </button>
        </div>
        <div class="week-body">
          <div v-for="row in weekSlots" :key="row.hour" class="week-row">
            <span class="time-gutter">{{ String(row.hour).padStart(2, '0') }}:00</span>
            <div v-for="cell in row.cells" :key="`${cell.key}-${row.hour}`" class="week-cell">
              <button
                v-if="cell.event"
                v-sketch
                class="chip sketch pencil-fill sketch-fill-only"
                type="button"
                :data-pencil="cell.category.pencil"
                :aria-label="cell.event.title"
                @click="selectDay(cell.key)"
              >{{ cell.event.chip }}</button>
            </div>
          </div>
        </div>
      </div>

      <ul class="legend">
        <li v-for="item in legend" :key="item.id" v-sketch class="legend-pill sketch sketch-white">
          <PencilSwatch :pencil="item.pencil" />{{ item.label }}
        </li>
      </ul>
    </article>

    <div class="agenda-head">
      <h2 v-sketch class="day-pill sketch pencil-fill" data-pencil="yellow">{{ selectedTitle }}</h2>
      <p>{{ selectedEvents.length }} 场活动 <AppIcon class="more" name="chevron" /></p>
    </div>

    <div v-if="selectedEvents.length" class="agenda">
      <article v-for="item in selectedEvents" :key="item.id" v-sketch class="event-card sketch sketch-white">
        <span class="accent" :data-accent="categoryOf(item).pencil" aria-hidden="true"></span>
        <RouterLink class="event-link" :to="{ path: '/detail', query: { id: item.id } }">
          <span v-sketch class="badge sketch pencil-fill" :data-pencil="categoryOf(item).pencil">
            <CalendarIcon :name="categoryOf(item).icon" />
          </span>
          <div class="event-copy">
            <div class="event-title">
              <p class="event-kind" :data-accent="categoryOf(item).pencil">{{ categoryOf(item).label }}</p>
              <h3>{{ item.title }}</h3>
            </div>
            <p class="event-meta">
              <span><CalendarIcon name="clock" />{{ item.start }}–{{ item.end }}</span>
              <span><AppIcon class="pin" name="pin" />{{ item.place }}</span>
            </p>
          </div>
        </RouterLink>
        <button
          class="save"
          type="button"
          :aria-pressed="saved.has(item.id)"
          :aria-label="saved.has(item.id) ? '取消收藏' : '收藏活动'"
          @click="toggleSave(item.id)"
        >
          <span
            v-if="saved.has(item.id)"
            v-sketch
            class="save-wash sketch pencil-fill sketch-fill-only"
            data-pencil="yellow"
            aria-hidden="true"
          ></span>
          <CalendarIcon class="save-icon" :class="{ 'is-on': saved.has(item.id) }" name="bookmark" />
        </button>
      </article>
    </div>
    <p v-else class="empty">这一天还没有安排活动</p>
  </section>
</template>

<style scoped>
.calendar-page { display: flex; flex-direction: column; flex-shrink: 0; padding-bottom: 12px; }
.toolbar { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin: 2px 0 12px; }
.title-block { display: flex; align-items: center; gap: 12px; min-width: 0; flex-wrap: wrap; }
.calendar-page h1 { position: relative; margin: 0; padding-bottom: 5px; font-size: 26px; line-height: 1.15; letter-spacing: .3px; }
.calendar-page h1::after { content: ''; position: absolute; left: 1px; right: 6px; bottom: 0; height: 4px; border-radius: 5px; background: #ffdf32; transform: rotate(-2deg); }
.lede { margin: 0; color: var(--muted); font-size: 13px; line-height: 1.3; }
.view-switch { position: relative; display: grid; grid-template-columns: 1fr 1fr; width: 124px; padding: 4px; background: transparent; flex: none; }
.view-tab { position: relative; z-index: 1; min-height: 36px; border: 0; border-radius: 0; background: transparent; font-size: 16px; color: var(--muted); }
.view-tab[aria-selected='true'] { color: var(--ink); }
.board { padding: 6px 8px 12px; background: transparent; }
.board-nav { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.board-title { margin: 0; flex: 1; text-align: center; font-size: 18px; letter-spacing: .4px; }
.nudge { width: 44px; height: 44px; border: 0; background: transparent; display: grid; place-items: center; color: var(--ink); }
.nudge-icon { width: 18px; height: 18px; }
.nudge-icon.is-left { transform: rotate(90deg); }
.nudge-icon:not(.is-left) { transform: rotate(-90deg); }
.month-head, .month-body { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); }
.month-head { margin: 2px 0 2px; color: var(--muted); font-size: 12px; text-align: center; }
.month-day { min-height: 54px; padding: 3px 0 4px; border: 0; background: transparent; display: flex; flex-direction: column; align-items: center; gap: 2px; color: inherit; font: inherit; }
.month-day.is-out { color: #b0b8c4; }
.month-day.is-today .day-num { color: #fff; }
.day-num { width: 28px; height: 28px; display: grid; place-items: center; font-size: 14px; line-height: 1; background: transparent; }
.dots { display: flex; justify-content: center; gap: 2px; min-height: 10px; }
.dots :deep(.swatch) { width: 8px; height: 8px; }
.today-tag { font-size: 9px; line-height: 1; color: #dc8289; }
.week-head, .week-row { display: grid; grid-template-columns: 36px repeat(7, minmax(0, 1fr)); gap: 2px; }
.week-day { min-height: 44px; padding: 1px 0 2px; border: 0; background: transparent; display: flex; flex-direction: column; align-items: center; gap: 1px; color: inherit; font: inherit; }
.week-label { font-size: 11px; color: var(--muted); line-height: 1.2; }
.week-body { margin-top: 2px; }
.week-row { min-height: 24px; align-items: stretch; border-top: 1px solid rgb(32 48 75 / 10%); }
.time-gutter { display: grid; place-items: center start; padding-left: 1px; color: var(--muted); font-size: 10px; letter-spacing: 0; }
.week-cell { min-width: 0; padding: 1px; display: flex; align-items: center; }
.chip { width: 100%; min-height: 22px; padding: 2px 2px; border: 0; background: transparent; color: var(--ink); font: inherit; font-size: 10px; line-height: 1.15; letter-spacing: 0; overflow: hidden; }
.legend { display: flex; gap: 8px; margin: 10px 2px 0; padding: 0; list-style: none; }
.legend-pill { flex: 1; min-height: 36px; display: inline-flex; align-items: center; justify-content: center; gap: 6px; padding: 6px 8px; background: transparent; color: var(--ink); font-size: 13px; }
.legend-pill :deep(.swatch) { width: 14px; height: 14px; }
.agenda-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin: 14px 0 10px; }
.day-pill { margin: 0; padding: 6px 12px; background: transparent; font-size: 15px; font-weight: 400; line-height: 1.2; }
.agenda-head p { margin: 0; color: var(--muted); font-size: 14px; display: inline-flex; align-items: center; gap: 2px; }
.more { width: 14px; height: 14px; transform: rotate(-90deg); }
.agenda { display: flex; flex-direction: column; gap: 10px; }
.event-card { position: relative; display: flex; align-items: stretch; background: transparent; }
.accent { width: 5px; margin: 12px 0 12px 8px; border-radius: 4px; flex: none; background: var(--ink); }
.accent[data-accent='pink'] { background: #e99796; }
.accent[data-accent='blue'] { background: #5ea7e5; }
.accent[data-accent='yellow'] { background: #f0b24a; }
.event-link { flex: 1; display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 8px; align-items: center; padding: 10px 40px 10px 8px; color: inherit; }
.badge { width: 40px; height: 40px; display: grid; place-items: center; background: transparent; color: var(--ink); }
.event-title { display: flex; align-items: baseline; flex-wrap: wrap; gap: 2px 8px; min-width: 0; }
.event-kind { margin: 0; font-size: 13px; line-height: 1.3; flex: none; }
.event-kind[data-accent='pink'] { color: #d56d68; }
.event-kind[data-accent='blue'] { color: #3d86c8; }
.event-kind[data-accent='yellow'] { color: #d89a22; }
.event-copy h3 { margin: 0; font-size: 16px; font-weight: 400; line-height: 1.3; min-width: 0; overflow-wrap: break-word; }
.event-meta { display: flex; flex-wrap: wrap; gap: 6px 12px; margin: 4px 0 0; color: var(--muted); font-size: 12px; line-height: 1.35; }
.event-meta span { display: inline-flex; align-items: center; gap: 4px; min-width: 0; }
.event-meta :deep(.cal-icon), .event-meta :deep(.icon) { width: 13px; height: 13px; }
.pin { color: #398def; fill: currentColor; stroke-width: 1.6; }
.save { position: absolute; top: 6px; right: 4px; width: 40px; height: 40px; border: 0; background: transparent; color: var(--ink); display: grid; place-items: center; }
.save-wash { position: absolute; inset: 6px; background: transparent; }
.save-icon { position: relative; width: 18px; height: 18px; }
.empty { margin: 8px 2px 0; color: var(--muted); font-size: 13px; }
@media (max-width: 359px) {
  .calendar-page h1 { font-size: 22px; }
  .lede, .event-copy h3 { font-size: 14px; }
  .board-title { font-size: 16px; }
  .view-switch { width: 104px; }
  .month-day { min-height: 48px; }
  .week-head, .week-row { grid-template-columns: 30px repeat(7, minmax(0, 1fr)); }
  .chip { font-size: 9px; }
  .legend { gap: 4px; }
  .legend-pill { font-size: 12px; padding-left: 4px; padding-right: 4px; }
  .event-title { flex-wrap: wrap; gap: 2px 8px; }
  .event-link { padding: 9px 36px 9px 6px; gap: 6px; }
}
</style>
