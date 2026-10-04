<script>
export const pageMeta = { key: 'map', id: 'D-02', title: '活动地图', placeholder: '地图主页', label: 'MAP', eyebrow: 'EXPLORE THE CAMPUS', icon: 'map', accent: 'blue', nav: 'map', back: false, immersive: true, heading: false };
</script>

<script setup>
import { computed, defineAsyncComponent, nextTick, onMounted, ref, watch } from 'vue';
import { RouterLink, useRoute } from 'vue-router';
import { saved, toggleSave, activityDetailRoute } from '../data/favorites.js';
import AppIcon from '../components/AppIcon.vue';
import ActivityDrawer from './map/ActivityDrawer.vue';
import mascot from '../../picture_reference/mascot.png';
import campus from '../../assets/maps/campus.json';
import { activities, categories, filters, venues } from './map/demo.js';
import { profileFor } from './map/model-profiles.mjs';
const CampusScene = defineAsyncComponent(() => import('./map/CampusScene.vue'));
const CampusPlan = defineAsyncComponent(() => import('./map/CampusPlan.vue'));
const route = useRoute(), focusPoint = ref(null), routedActivity = ref(null);
const mode = ref('3d'), filter = ref('all'), search = ref(''), selected = ref(null), floor = ref(2), scene = ref(null), located = ref(false), detail = ref(null);
const drawer = ref(null), drawerPeek = ref(180);
const planView = ref(null);
let drawerBeforeSelection = null;
const campusActivities = activities.filter(item => item.building);
const visibleActivities = computed(() => campusActivities.filter(item => filter.value === 'all' || item.category === filter.value));
const currentBuilding = computed(() => {
  if (!selected.value) return null;
  const building = campus.buildings.find(b => b.id === selected.value), venue = venues.find(v => v.id === selected.value);
  const profile = building ? profileFor(building) : {};
  return { ...building, ...venue, short: venue?.short || building?.name || '校园建筑', floors: venue?.floors || Math.min(6, profile.floors || 3), scenic: profile.scenic };
});
const floorActivities = computed(() => visibleActivities.value.filter(a => a.building === selected.value && a.floor === floor.value));
const buildingWalk = computed(() => {
  const meters = Math.min(...activities.filter(item => item.building === selected.value).map(item => Number.parseInt(item.distance, 10)));
  if (!Number.isFinite(meters)) return '校园内';
  return `距你 ${meters}m · 步行 ${Math.max(1, Math.round(meters / 70))} 分钟`;
});
const results = computed(() => {
  const value = search.value.trim().toLowerCase();
  if (!value) return [];
  return campus.buildings.filter(b => b.name.toLowerCase().includes(value) || activities.some(a => a.building === b.id && `${a.title}${a.room}`.toLowerCase().includes(value))).slice(0, 6);
});
const venuePage = ref(0), activityPage = ref(0), likedPage = ref(0);
const showAllLiked = ref(false);
const likedPreview = [...campusActivities].sort(() => Math.random() - 0.5).slice(0, 3);
const likedActivities = computed(() => showAllLiked.value ? campusActivities : likedPreview);
function showAll(section) {
  filter.value = 'all';
  if (section === 'liked') showAllLiked.value = true;
}
const buildingPalette = ['pink', 'yellow', 'blue', 'mint'];
const venuePencil = Object.fromEntries([...venues].sort(() => Math.random() - 0.5).map((venue, index) => [venue.id, buildingPalette[index % buildingPalette.length]]));
const venueCards = computed(() => venues.map(venue => {
  const meters = Math.min(...campusActivities.filter(item => item.building === venue.id).map(item => Number.parseInt(item.distance, 10) || 0));
  const safe = Number.isFinite(meters) ? meters : 0;
  return { ...venue, distanceLabel: safe ? `${safe} m` : '校园内', minutes: Math.max(1, Math.round((safe || 80) / 70)), pencil: venuePencil[venue.id] };
}));
function activityIcon(type) { return categories[type]?.icon || 'star'; }
function floorActivityIcon(type) { return categories[type]?.floorIcon || 'flag'; }
function activityPencil(type) { return categories[type]?.pencil || 'yellow'; }
const pencilInk = { yellow: '#ffdf32', blue: '#9ac8f2', mint: '#7ec9a8', pink: '#f4b2ab', lavender: '#c9b6f0' };
function activityInk(type) { return pencilInk[activityPencil(type)] || pencilInk.yellow; }
function buildingPencil(id) { return venuePencil[id] || 'yellow'; }
function roomLabel(activity) { return /^\d/.test(activity.room) ? `${currentBuilding.value?.label || '教室'} ${activity.room}` : activity.room; }
function startTime(time) { return time.split('–')[0]; }
function syncPage(event, which) {
  const card = event.currentTarget.firstElementChild;
  if (!card) return;
  const index = Math.max(0, Math.round(event.currentTarget.scrollLeft / (card.offsetWidth + 10)));
  if (which === 'venue') venuePage.value = index;
  else if (which === 'liked') likedPage.value = index;
  else activityPage.value = index;
}
function placeLine(activity) {
  const venue = venues.find(item => item.id === activity.building);
  return [venue?.short || activity.place || '校园', `${activity.floor}F`, activity.room].filter(Boolean).join(' · ');
}
function openActivity(activity) {
  if (!activity?.building) return;
  if (!selected.value) drawerBeforeSelection = drawer.value?.getState() ?? 'middle';
  selected.value = activity.building;
  floor.value = activity.floor || 1;
  detail.value = activity;
  search.value = '';
  drawer.value?.setState('expanded');
  nextTick(() => window.HandDrawn?.refresh());
}
function closeDetail() {
  detail.value = null;
  drawer.value?.setState(drawer.value?.getState() || 'expanded');
  nextTick(() => window.HandDrawn?.refresh());
}
function select(id) {
  focusPoint.value = null; routedActivity.value = null; detail.value = null;
  if (id) {
    // 只记录进入建筑探索前的档位，切换建筑或查看详情不覆盖这份状态。
    if (!selected.value) drawerBeforeSelection = drawer.value?.getState() ?? 'middle';
    drawer.value?.collapse();
  } else {
    if (drawerBeforeSelection !== null) drawer.value?.setState(drawerBeforeSelection);
    drawerBeforeSelection = null;
  }
  selected.value = id; search.value = '';
  floor.value = visibleActivities.value.find(a => a.building === id)?.floor || 1;
}
async function locate() {
  // 复位只调整地图，保留操作当下的抽屉档位；结束本次建筑探索记录。
  drawerBeforeSelection = null; located.value = true; selected.value = null; detail.value = null; focusPoint.value = null; routedActivity.value = null;
  await nextTick(); scene.value?.locate();
}
async function setMode(value) {
  if (value === mode.value) return;
  if (mode.value === '2d') planView.value = scene.value?.getView();
  // 两种地图共用建筑、楼层和抽屉状态，切换后继续查看同一处活动。
  mode.value = value; search.value = '';
  await nextTick();
  window.HandDrawn?.refresh();
}
async function applyActivityRoute() {
  const raw = route.query.activity;
  const id = Array.isArray(raw) ? raw[0] : raw;
  const item = activities.find(activity => activity.id === id);
  if (!item) return;
  filter.value = 'all'; mode.value = '3d';
  await nextTick();
  if (item.building) openActivity(item);
  else select(null);
  floor.value = item.floor || 1;
  focusPoint.value = item.mapPosition || null;
  routedActivity.value = item;
}
onMounted(applyActivityRoute);
watch(() => route.query.activity, applyActivityRoute);
</script>

<template>
  <section id="page-title" class="map-page" aria-label="燕园活动探索" tabindex="-1">
    <div class="map-rule" aria-hidden="true"></div>
    <div class="map-stage" :class="{ 'building-focus': selected, 'plan-mode': mode === '2d' }" :style="{ '--drawer-peek': `${drawerPeek}px` }">
      <CampusScene v-if="mode === '3d'" ref="scene" :focus-inset="drawerPeek" :focus-point="focusPoint" :selected="selected" :floor="floor" :activities="visibleActivities" @select="select" @floor="floor = $event" />
      <CampusPlan v-else ref="scene" :focus-inset="drawerPeek" :focus-point="focusPoint" :selected="selected" :activities="visibleActivities" :starting-view="planView" @select="select" />
        <span v-if="mode === '3d'" class="campus-caption">北京大学 · 燕园</span>
        <div class="map-hint">{{ routedActivity ? `${routedActivity.title}${focusPoint ? ' · 地点示意' : ` · ${floor}F`}` : mode === '2d' ? selected ? '俯视建筑 · 在下方切换楼层查看活动' : '点建筑查看活动 · 拖动平移 · 双指缩放' : currentBuilding?.scenic ? '拖动环绕博雅塔 · 缩小看看未名湖' : selected ? '点楼层查看活动 · 拖动查看另一侧' : '点建筑，看看楼层里正在发生什么' }}</div>
      <div class="map-overlay">
      <div class="map-search-wrap">
        <label v-sketch class="map-search sketch sketch-white"><AppIcon name="pin" /><input v-model="search" type="search" placeholder="找建筑、教室或活动…" aria-label="搜索燕园建筑、教室或活动" autocomplete="off" /><span class="search-campus">燕园</span></label>
        <div v-if="search.trim()" class="search-results" role="region" aria-label="本地搜索结果">
          <button v-for="building in results" :key="building.id" @click="select(building.id)"><AppIcon name="map" /><span>{{ building.name }}</span><span>↗</span></button>
          <p v-if="!results.length">没有找到，试试「理科」「208」或「电影」。</p>
        </div>
      </div>
      <div class="filter-row" aria-label="活动分类">
        <button v-for="item in filters" :key="`${item.id}-${filter === item.id}`" v-sketch class="filter-chip sketch sketch-cast" :class="filter === item.id ? 'pencil-fill' : 'sketch-white'" :data-pencil="filter === item.id ? item.pencil : undefined" :data-cast="item.pencil" :aria-pressed="filter === item.id" @click="filter = item.id">{{ item.label }}</button>
        <span class="demo-stamp">今日 · 演示</span>
      </div>
      </div>
      <div class="map-rail">
        <div v-sketch class="mode-switch sketch sketch-white sketch-cast" data-cast="blue" role="tablist" aria-label="地图显示模式">
          <button v-for="item in ['3d', '2d']" :key="`${item}-${mode === item}`" v-sketch class="mode-tab" :class="mode === item ? 'sketch pencil-fill sketch-fill-only' : ''" :data-pencil="mode === item ? 'blue' : undefined" type="button" role="tab" :aria-selected="mode === item" @click="setMode(item)">{{ item.toUpperCase() }}</button>
        </div>
        <div class="map-tools" aria-label="地图控制">
          <button v-sketch class="sketch" aria-label="放大地图" @click="scene?.zoom(.8)">＋</button>
          <button v-sketch class="sketch" aria-label="缩小地图" @click="scene?.zoom(1.25)">−</button>
          <button v-sketch class="sketch locate-button" :data-pencil="located ? 'blue' : undefined" aria-label="查看示例定位附近的活动" @click="locate">◎</button>
        </div>
      </div>
    </div>
    <ActivityDrawer ref="drawer" @measure="drawerPeek = $event">
      <template v-if="detail">
        <section class="activity-intro" :aria-label="detail.title" :style="{ '--intro-ink': activityInk(detail.category) }">
          <span v-sketch class="intro-pill sketch pencil-fill sketch-cast" :data-pencil="activityPencil(detail.category)" :data-cast="activityPencil(detail.category)"><i :style="{ background: categories[detail.category].mark }"></i>{{ detail.label }}</span>
          <div class="intro-title-row">
            <h2 v-sketch :key="detail.id" class="intro-name sketch pencil-fill sketch-cast" :data-pencil="activityPencil(detail.category)" :data-cast="activityPencil(detail.category)">{{ detail.title }}</h2>
            <div class="intro-actions">
              <button class="intro-save" type="button" :aria-pressed="saved.has(detail.id)" :aria-label="saved.has(detail.id) ? '取消收藏' : '收藏活动'" @click="toggleSave(detail.id)">
                <span v-if="saved.has(detail.id)" v-sketch :key="detail.category" class="bookmark-pencil sketch pencil-fill sketch-fill-only" :data-pencil="activityPencil(detail.category)"></span>
                <svg viewBox="0 0 24 32" aria-hidden="true"><path d="M4 2.5h16v26l-8-6-8 6Z" /></svg>
              </button>
              <button class="intro-back" type="button" aria-label="返回楼层地图" @click="closeDetail"><AppIcon name="back" /></button>
            </div>
          </div>
          <p class="intro-fact"><svg class="intro-solid" viewBox="0 0 32 32" aria-hidden="true"><path fill="currentColor" fill-rule="evenodd" d="M16 4a12 12 0 1 0 .01 0ZM15 9h2v7.2l4.2 2.4-1 1.7-5.2-3V9Z" /></svg><strong>{{ detail.time.replace('–', '-') }}</strong></p>
          <p class="intro-fact"><svg class="intro-solid" viewBox="0 0 32 32" aria-hidden="true"><path fill="currentColor" fill-rule="evenodd" d="M16 2a10 10 0 0 0-10 11c0 8 10 17 10 17s10-9 10-17A10 10 0 0 0 16 2Zm0 7.5a3.5 3.5 0 1 1 0 7 3.5 3.5 0 0 1 0-7Z" /></svg><strong>{{ placeLine(detail) }}</strong></p>
          <h3 class="intro-heading">活动简介<AppIcon class="title-spark" name="spark" /></h3>
          <p class="intro-copy">{{ detail.description }}</p>
          <RouterLink v-sketch class="intro-more sketch pencil-fill sketch-cast" data-pencil="yellow" data-cast="yellow" :to="activityDetailRoute(detail)">查看活动详情 <AppIcon name="chevron" /></RouterLink>
        </section>
      </template>
      <template v-else-if="currentBuilding">
        <div class="building-head">
          <span v-sketch class="building-mark sketch pencil-fill sketch-cast" :data-pencil="buildingPencil(currentBuilding.id)" :data-cast="buildingPencil(currentBuilding.id)" aria-hidden="true">
            <svg class="building-art" viewBox="0 0 48 48"><circle cx="9" cy="27" r="5" fill="#7dbe78"/><circle cx="39" cy="28" r="4.2" fill="#8fce86"/><path d="M8.2 31.5v6M38.4 32v5" stroke="#5f8a58" stroke-width="1.6"/><path d="M16 20.5 24 13l8 7.5" fill="#f4d2c4" stroke="#20304b" stroke-width="1.4" stroke-linejoin="round"/><path d="M17 20.5h14V36H17Z" fill="#fffaf3" stroke="#20304b" stroke-width="1.4"/><path d="M22 36V25.5h4V36M28 36V25.5h3.2" fill="none" stroke="#20304b" stroke-width="1.3"/></svg>
          </span>
          <div class="building-copy">
            <h2>{{ currentBuilding.name || currentBuilding.short }}</h2>
            <p>{{ currentBuilding.scenic ? '燕园地标' : buildingWalk }}<span v-if="!currentBuilding.scenic" class="open-chip">开放中</span></p>
          </div>
          <button class="building-back" type="button" aria-label="返回" @click="select(null)"><AppIcon name="back" /></button>
        </div>
        <p v-if="currentBuilding.scenic" class="landmark-note">未名湖东南的十三重密檐塔。{{ mode === '2d' ? '俯视图展示塔顶与湖岸位置，切换 3D 可环绕查看塔身。' : '保留完整外观，拖动地图可环绕查看塔身与湖岸。' }}<small>外观为实景特征的简化建模 · 此地标暂无示例活动</small></p>
        <template v-else>
          <div v-sketch class="floor-switch sketch sketch-white" role="tablist" aria-label="选择建筑楼层">
            <button v-for="number in currentBuilding.floors" :key="`${number}-${floor === number}`" v-sketch class="floor-tab" :class="floor === number ? 'sketch pencil-fill sketch-fill-only' : ''" :data-pencil="floor === number ? 'blue' : undefined" type="button" role="tab" :aria-selected="floor === number" @click="floor = number">{{ number }}F</button>
          </div>
          <div class="floor-head">
            <div class="block-title"><h2>{{ floor }}F 活动</h2><AppIcon class="title-spark" name="spark" /></div>
            <span class="floor-count">今天 {{ floorActivities.length }} 场</span>
          </div>
          <button v-for="activity in floorActivities" :key="activity.id" v-sketch class="floor-activity sketch sketch-white sketch-cast" :data-cast="activityPencil(activity.category)" type="button" @click="openActivity(activity)">
            <span v-sketch class="activity-mark sketch pencil-fill sketch-cast" :data-pencil="activityPencil(activity.category)" :data-cast="activityPencil(activity.category)"><AppIcon :name="floorActivityIcon(activity.category)" /></span>
            <span class="activity-body"><span class="activity-kind">{{ activity.label }}</span><strong>{{ activity.title }}</strong><span class="activity-meta"><span><AppIcon name="clock" />{{ activity.time }}</span><span><AppIcon name="pin" />{{ roomLabel(activity) }}</span></span></span>
            <AppIcon class="card-forward" name="chevron" />
          </button>
          <p v-if="!floorActivities.length" class="floor-empty">这一层先留一点空白，等新的校园故事。<br>可切换楼层或活动分类继续探索。</p>
        </template>
      </template>
      <template v-else>
        <section class="nearby-block">
          <div class="block-head">
            <div class="block-title"><AppIcon class="title-spark" name="spark" /><h2>附近建筑</h2><AppIcon class="title-spark is-right" name="spark" /></div>
            <button class="see-all" type="button" @click="showAll('venue')">查看全部 <AppIcon name="chevron" /></button>
          </div>
          <div class="snap-row" aria-label="附近建筑" @scroll.passive="syncPage($event, 'venue')">
            <button v-for="venue in venueCards" :key="venue.id" v-sketch class="place-card sketch sketch-white sketch-cast" :data-cast="venue.pencil" @click="select(venue.id)">
              <span v-sketch class="place-badge sketch pencil-fill sketch-cast" :data-pencil="venue.pencil" :data-cast="venue.pencil"><AppIcon name="pin" /></span>
              <span class="place-copy"><strong>{{ venue.short }}</strong><span>{{ venue.distanceLabel }} · 步行 {{ venue.minutes }} 分钟</span></span>
              <AppIcon class="card-forward" name="chevron" />
            </button>
          </div>
          <div class="pager" aria-hidden="true"><span v-for="(venue, index) in venueCards" :key="venue.id" :class="{ on: venuePage === index }"></span></div>
        </section>
        <section class="nearby-block">
          <div class="block-head">
            <div class="block-title"><AppIcon class="title-spark" name="spark" /><h2>附近活动</h2><AppIcon class="title-spark is-right" name="spark" /></div>
            <button class="see-all" type="button" @click="showAll('activity')">查看全部 <AppIcon name="chevron" /></button>
          </div>
          <div class="snap-row" aria-label="附近活动" @scroll.passive="syncPage($event, 'activity')">
            <button v-for="activity in visibleActivities" :key="activity.id" v-sketch class="event-card sketch sketch-white sketch-cast" :data-cast="activityPencil(activity.category)" @click="openActivity(activity)">
              <span v-sketch class="place-badge sketch pencil-fill sketch-cast" :data-pencil="activityPencil(activity.category)" :data-cast="activityPencil(activity.category)"><AppIcon :name="activityIcon(activity.category)" /></span>
              <span class="event-copy"><small>{{ activity.label }}</small><strong>{{ activity.title }}</strong><span><AppIcon name="pin" />{{ activity.distance }} · {{ startTime(activity.time) }}</span></span>
              <AppIcon class="card-forward" name="chevron" />
            </button>
          </div>
          <p v-if="!visibleActivities.length" class="floor-empty">这个分类下还没有示例活动。</p>
          <div v-else class="pager" aria-hidden="true"><span v-for="(activity, index) in visibleActivities" :key="activity.id" :class="{ on: activityPage === index }"></span></div>
        </section>
        <section class="nearby-block">
          <div class="block-head">
            <div class="block-title"><AppIcon class="title-spark" name="spark" /><h2>猜你喜欢</h2><AppIcon class="title-spark is-right" name="spark" /></div>
            <button class="see-all" type="button" @click="showAll('liked')">查看全部 <AppIcon name="chevron" /></button>
          </div>
          <div class="snap-row" aria-label="猜你喜欢" @scroll.passive="syncPage($event, 'liked')">
            <button v-for="activity in likedActivities" :key="activity.id" v-sketch class="event-card sketch sketch-white sketch-cast" :data-cast="activityPencil(activity.category)" @click="openActivity(activity)">
              <span v-sketch class="place-badge sketch pencil-fill sketch-cast" :data-pencil="activityPencil(activity.category)" :data-cast="activityPencil(activity.category)"><AppIcon :name="activityIcon(activity.category)" /></span>
              <span class="event-copy"><small>{{ activity.label }}</small><strong>{{ activity.title }}</strong><span><AppIcon name="pin" />{{ activity.distance }} · {{ startTime(activity.time) }}</span></span>
              <AppIcon class="card-forward" name="chevron" />
            </button>
          </div>
          <div class="pager" aria-hidden="true"><span v-for="(activity, index) in likedActivities" :key="activity.id" :class="{ on: likedPage === index }"></span></div>
        </section>
        <section class="agent-promo">
          <div v-sketch class="agent-bubble sketch sketch-white sketch-cast" data-cast="blue">
            <h2><span>不知道去哪？</span><svg class="bubble-rays" viewBox="0 0 36 28" aria-hidden="true"><path d="M4 18c7-1 12-2 18-4" /><path d="M8 24c7-3 13-8 18-13" /><path d="M16 26c4-5 7-11 9-17" /></svg></h2>
            <p>让LiLi为你推荐路线与活动！</p>
            <svg class="bubble-tail" viewBox="0 0 32 40" aria-hidden="true"><path d="M2 7c6 3 13 7 20 11-5 2-13 6-19 9" fill="none" stroke="#78b8ed" stroke-width="3.6" stroke-linecap="round" transform="translate(2.4 2.6)" opacity=".78"/><path d="M4 8c5 2 10 5 15 8" fill="none" stroke="#4f95d2" stroke-width="1.8" stroke-linecap="round" transform="translate(3.2 3.4)" opacity=".55"/><path d="M1 4c7 4 14 8 22 13-7 3-15 8-22 12z" fill="#fff"/><path d="M2 6c6 3 13 7 20 11-5 2-13 6-19 9" fill="none" stroke="#20304b" stroke-width="1.7" stroke-linecap="round"/><path d="M3 7.2c5 2.4 11 6 17 9" fill="none" stroke="#20304b" stroke-width=".7" opacity=".5" stroke-linecap="round"/></svg>
          </div>
          <RouterLink v-sketch class="ask-agent sketch pencil-fill sketch-cast" data-pencil="yellow" data-cast="yellow" to="/agent">问问小助手 <AppIcon name="chevron" /></RouterLink>
          <img class="agent-mascot" :src="mascot" alt="" />
        </section>
      </template>
    </ActivityDrawer>
  </section>
</template>

<style scoped>
.map-page { position: relative; display: flex; flex: 1; flex-direction: column; min-width: 0; min-height: 0; outline: none; }
.map-rule { height: 1.5px; flex: 0 0 auto; background: #20304b; }
.map-overlay { position: absolute; top: 8px; left: 0; right: 0; z-index: 8; pointer-events: none; }
.map-search-wrap { position: relative; z-index: 2; margin: 0 17px; pointer-events: auto; }
.map-search { display: flex; align-items: center; gap: 7px; padding: 4px 12px; min-height: 44px; }
.map-search .icon { width: 18px; height: 18px; }
.map-search input { font: inherit; background: transparent; border: 0; color: var(--ink); width: 100%; min-width: 0; font-size: 12px; outline: none; padding: 6px 0; }
.map-search:focus-within { outline: 2px solid #82acd0; outline-offset: 2px; border-radius: 12px; }
.search-campus { font-size: 10px; white-space: nowrap; color: var(--muted); border-left: 1px solid #c8caca; padding-left: 9px; }
.search-results { position: absolute; top: calc(100% + 5px); left: 0; right: 0; padding: 6px 8px; background: #fffdf5; border: 1px solid #87939d; border-radius: 12px; box-shadow: 0 6px 20px #20304b20; }
.search-results button { display: flex; gap: 7px; width: 100%; padding: 12px 4px; align-items: center; background: transparent; border: 0; text-align: left; font-size: 12px; }
.search-results button span:last-child { margin-left: auto; }.search-results .icon { width: 15px; height: 15px; }.search-results p { font-size: 12px; }
.filter-row { display: flex; align-items: center; gap: 6px; padding: 8px 17px 0; pointer-events: auto; }
.filter-chip { flex: none; padding: 7px 10px; min-height: 36px; font-size: 12px; white-space: nowrap; background: transparent; }.demo-stamp { margin-left: auto; font-size: 10px; color: #899287; white-space: nowrap; }
.map-stage { position: relative; min-height: 0; flex: 1; overflow: hidden; background: var(--blue); }
.map-rail { position: absolute; right: 12px; top: 104px; z-index: 6; display: flex; flex-direction: column; align-items: center; gap: 8px; }
.mode-switch { display: grid; grid-template-columns: 1fr; width: 44px; padding: 3px; background: transparent; }
.mode-tab { min-height: 34px; border: 0; background: transparent; font-size: 11px; color: var(--ink); padding: 4px 0; }
.campus-caption { position: absolute; top: 108px; left: 15px; font-size: 11px; color: #6a7c78; pointer-events: none; }
.map-tools { display: grid; gap: 6px; }
.map-tools button { width: 36px; height: 36px; padding: 0; font-size: 21px; background: transparent; }.map-tools .locate-button { font-size: 23px; }
.map-hint { position: absolute; left: 15px; bottom: calc(var(--drawer-peek) + 24px); font-size: 10px; color: #526663; background: #f8f8efc4; padding: 4px 7px; border-radius: 6px; pointer-events: none; }
h2 { font-size: 19px; line-height: 1.4; font-weight: 400; margin: 0; }
.building-head { display: flex; align-items: center; gap: 10px; }
.building-mark { display: grid; place-items: center; width: 52px; height: 52px; flex: none; }
.building-art { width: 40px; height: 40px; }
.building-copy { min-width: 0; flex: 1; }
.building-copy h2 { font-size: 18px; line-height: 1.25; -webkit-text-stroke: .25px var(--ink); }
.building-copy p { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin: 4px 0 0; font-size: 11px; color: #66788a; }
.open-chip { display: inline-flex; align-items: center; padding: 1px 8px 2px; border-radius: 999px; background: #d7eefc; color: #2a6eae; font-size: 11px; line-height: 1.45; }
.building-back { width: 36px; height: 36px; flex: none; border: 0; background: transparent; padding: 4px; }
.building-back .icon { width: 22px; height: 22px; }
.floor-switch { display: grid; grid-auto-flow: column; grid-auto-columns: 1fr; margin-top: 14px; padding: 3px; background: transparent; }
.floor-tab { position: relative; width: 100%; min-height: 40px; border: 0; background: transparent; font-size: 15px; color: var(--ink); }
.floor-tab + .floor-tab::before { content: ''; position: absolute; left: 0; top: 22%; bottom: 22%; width: 1.5px; background: #20304b; }
.floor-tab[aria-selected='true']::before, .floor-tab[aria-selected='true'] + .floor-tab::before { opacity: 0; }
.floor-head { display: flex; align-items: flex-end; justify-content: space-between; gap: 8px; margin: 16px 2px 8px; }
.floor-count { font-size: 12px; color: #66788a; white-space: nowrap; }
.floor-activity { display: flex; align-items: center; gap: 10px; width: 100%; min-height: 78px; margin-top: 8px; padding: 10px 12px; background: transparent; text-align: left; }
.activity-mark { display: grid; place-items: center; width: 46px; height: 46px; flex: none; }
.activity-mark .icon { width: 24px; height: 24px; }
.activity-body { display: grid; gap: 3px; min-width: 0; }
.activity-kind { justify-self: start; padding: 0 7px; border: 1.4px solid #20304b; border-radius: 999px; background: #fffdf8; font-size: 10px; line-height: 1.6; }
.activity-body strong { font-weight: 400; font-size: 15px; line-height: 1.3; }
.activity-meta { display: flex; flex-wrap: wrap; gap: 8px 12px; }
.activity-meta span { display: inline-flex; align-items: center; gap: 3px; font-size: 11px; color: #66788a; }
.activity-meta .icon { width: 13px; height: 13px; }
.nearby-block { margin-bottom: 4px; }
.block-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.block-title { position: relative; display: inline-flex; align-items: center; gap: 4px; }
.block-title h2 { margin: 0; font-size: 22px; line-height: 1.2; background: linear-gradient(#ffe56a, #ffe56a) left 78% / 100% 8px no-repeat; }
.title-spark { width: 12px; height: 12px; color: #f2c431; flex: none; }
.title-spark.is-right { transform: rotate(18deg); }
.see-all { display: inline-flex; align-items: center; gap: 2px; border: 0; background: transparent; color: #2f78c4; font-size: 13px; padding: 0; white-space: nowrap; }
.see-all .icon { width: 14px; height: 14px; transform: rotate(-90deg); }
.snap-row { display: flex; gap: 10px; overflow-x: auto; scroll-snap-type: x mandatory; scrollbar-width: none; padding: 4px 8px 12px 2px; }
.snap-row::-webkit-scrollbar { display: none; }
.place-card, .event-card { display: flex; align-items: center; gap: 8px; flex: 0 0 78%; scroll-snap-align: start; min-height: 74px; padding: 10px; text-align: left; background: transparent; }
.place-badge { display: grid; place-items: center; width: 42px; height: 42px; flex: none; }
.place-badge .icon { width: 22px; height: 22px; }
.place-copy, .event-copy { display: grid; gap: 3px; min-width: 0; }
.place-copy strong, .event-copy strong { font-weight: 400; font-size: 15px; line-height: 1.25; }
.place-copy span, .event-copy > span { display: flex; align-items: center; gap: 3px; font-size: 11px; color: #66788a; }
.place-copy .icon, .event-copy .icon { width: 12px; height: 12px; flex: none; }
.event-copy small { font-size: 10px; color: #7d8b9c; }
.card-forward { width: 16px; height: 16px; margin-left: auto; flex: none; transform: rotate(-90deg); }
.pager { display: flex; justify-content: center; gap: 6px; margin: 0 0 12px; }
.pager span { width: 6px; height: 6px; border-radius: 50%; background: #d5dbe3; }
.pager span.on { background: #20304b; }
.agent-promo { display: grid; grid-template-columns: minmax(0, 1fr) 112px; align-items: center; column-gap: 8px; row-gap: 10px; margin-top: 18px; }
.agent-bubble { position: relative; z-index: 0; grid-column: 1; grid-row: 1; margin-right: 6px; padding: 11px 14px 10px 30px; background: transparent; }
.agent-bubble h2 { display: flex; align-items: center; gap: 2px; margin: 0; font-size: 20px; line-height: 1.2; -webkit-text-stroke: .3px var(--ink); }
.agent-bubble h2 span { white-space: nowrap; background: linear-gradient(#ffe56a, #ffe56a) left 70% / 100% 10px no-repeat; box-decoration-break: clone; -webkit-box-decoration-break: clone; }
.agent-bubble p { margin: 5px 0 0; font-size: 13px; line-height: 1.4; color: #5d6d80; }
.bubble-rays { width: 28px; height: 22px; flex: none; margin-top: 1px; fill: none; stroke: #ffd600; stroke-width: 3.2; stroke-linecap: round; }
.bubble-tail { position: absolute; right: -18px; bottom: 6px; width: 30px; height: 38px; overflow: visible; pointer-events: none; }
.agent-mascot { grid-column: 2; grid-row: 1 / span 2; width: 112px; height: 112px; justify-self: center; align-self: center; object-fit: contain; }
.ask-agent { grid-column: 1; grid-row: 2; justify-self: start; align-self: start; display: inline-flex; align-items: center; gap: 6px; min-height: 44px; margin: 0 0 0 16px; padding: 8px 18px; background: transparent; font-size: 16px; }
.ask-agent .icon { width: 16px; height: 16px; transform: rotate(-90deg); }
.landmark-note { font-size: 12px; line-height: 1.8; color: #657e6e; margin: 12px 0; }.landmark-note small { display: block; margin-top: 7px; font-size: 9px; color: #8c968f; }
.floor-empty { text-align: center; padding: 16px 0; font-size: 12px; color: #8c9c95; line-height: 1.8; }
.activity-intro { display: grid; gap: 12px; padding-bottom: 8px; }
.intro-pill { justify-self: start; display: inline-flex; align-items: center; gap: 6px; min-height: 28px; padding: 2px 10px; background: transparent; font-size: 13px; }
.intro-pill i { width: 8px; height: 8px; border-radius: 50%; }
.intro-title-row { display: flex; align-items: flex-start; gap: 8px; margin-top: -8px; }
.intro-actions { display: flex; align-items: center; gap: 0; flex: none; margin-left: auto; }
.intro-back { width: 36px; height: 36px; border: 0; background: transparent; padding: 6px; }
.intro-back .icon { width: 22px; height: 22px; }
.intro-save { position: relative; display: grid; place-items: center; width: 36px; height: 36px; border: 0; background: transparent; padding: 6px; }
.bookmark-pencil { position: absolute; left: 50%; top: 50%; width: 128px; height: 176px; margin: -88px 0 0 -64px; border: 0; transform: scale(.125); pointer-events: none; clip-path: polygon(16.7% 7.8%, 83.3% 7.8%, 83.3% 89.1%, 50% 70.3%, 16.7% 89.1%); }
.intro-save svg { position: relative; z-index: 1; width: 16px; height: 22px; fill: transparent; stroke: var(--ink); stroke-width: 1.8; stroke-linejoin: round; }
.intro-name { width: max-content; max-width: calc(100% - 80px); margin: 0; padding: 10px 14px; font-size: 28px; font-weight: 400; line-height: 1.2; }
.intro-fact { display: flex; align-items: center; gap: 10px; margin: 0; }
.intro-solid { width: 22px; height: 22px; flex: none; color: var(--ink); }
.intro-fact strong { font-weight: 400; font-size: 16px; }
.intro-heading { display: inline-flex; align-items: center; gap: 4px; margin: 4px 0 0; font-size: 20px; font-weight: 400; background: linear-gradient(var(--intro-ink), var(--intro-ink)) left 78% / 4.2em 8px no-repeat; }
.intro-heading .title-spark { color: var(--intro-ink); }
.intro-copy { margin: 0; font-size: 14px; line-height: 1.55; }
.intro-more { justify-self: start; display: inline-flex; align-items: center; gap: 6px; min-height: 44px; margin-top: 4px; padding: 8px 18px; background: transparent; font-size: 16px; }
.intro-more .icon { width: 16px; height: 16px; transform: rotate(-90deg); }
@media (max-width: 359px) { .filter-row { gap: 3px; }.filter-chip { padding: 7px 8px; }.map-search-wrap { margin: 0 15px; }.building-copy h2, .activity-body strong { font-size: 14px; }.activity-meta span { font-size: 10px; }.agent-promo { grid-template-columns: minmax(0, 1fr) 88px; }.agent-bubble h2 { font-size: 18px; }.agent-bubble p { font-size: 12px; }.agent-mascot { width: 88px; height: 88px; } }
</style>
