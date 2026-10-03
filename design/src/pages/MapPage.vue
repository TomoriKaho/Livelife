<script>
export const pageMeta = { key: 'map', id: 'D-02', title: '活动地图', placeholder: '地图主页', label: 'MAP', eyebrow: 'EXPLORE THE CAMPUS', icon: 'map', accent: 'blue', nav: 'map', back: false, immersive: true };
</script>

<script setup>
import { computed, defineAsyncComponent, nextTick, ref } from 'vue';
import { RouterLink } from 'vue-router';
import AppIcon from '../components/AppIcon.vue';
import ActivityDrawer from './map/ActivityDrawer.vue';
import campus from '../../assets/maps/campus.json';
import { activities, filters, venues } from './map/demo.js';
import { profileFor } from './map/model-profiles.mjs';
const CampusScene = defineAsyncComponent(() => import('./map/CampusScene.vue'));
const mode = ref('3d'), filter = ref('all'), search = ref(''), selected = ref(null), floor = ref(2), scene = ref(null), located = ref(false), detail = ref(null), dialog = ref(null);
const drawer = ref(null), drawerPeek = ref(180);
let drawerBeforeSelection = null;
const visibleActivities = computed(() => activities.filter(a => filter.value === 'all' || a.type === filter.value));
const currentBuilding = computed(() => {
  if (!selected.value) return null;
  const building = campus.buildings.find(b => b.id === selected.value), venue = venues.find(v => v.id === selected.value);
  const profile = building ? profileFor(building) : {};
  return { ...building, ...venue, short: venue?.short || building?.name || '校园建筑', floors: venue?.floors || Math.min(6, profile.floors || 3), scenic: profile.scenic };
});
const floorActivities = computed(() => visibleActivities.value.filter(a => a.building === selected.value && a.floor === floor.value));
const results = computed(() => {
  const value = search.value.trim().toLowerCase();
  if (!value) return [];
  return campus.buildings.filter(b => b.name.toLowerCase().includes(value) || activities.some(a => a.building === b.id && `${a.title}${a.room}`.toLowerCase().includes(value))).slice(0, 6);
});
const today = computed(() => visibleActivities.value.slice(0, 3));
function select(id) {
  if (id) {
    // 只记录进入建筑探索前的档位，切换建筑或查看详情不覆盖这份状态。
    if (!selected.value) drawerBeforeSelection = drawer.value?.getState() ?? 'middle';
    drawer.value?.collapse();
  } else {
    if (drawerBeforeSelection !== null) drawer.value?.setState(drawerBeforeSelection);
    drawerBeforeSelection = null;
  }
  selected.value = id; search.value = ''; mode.value = '3d';
  floor.value = visibleActivities.value.find(a => a.building === id)?.floor || 1;
}
async function openActivity(activity) { detail.value = activity; await nextTick(); dialog.value.showModal(); }
async function locate() {
  // 复位只调整地图，保留操作当下的抽屉档位；结束本次建筑探索记录。
  drawerBeforeSelection = null; located.value = true; selected.value = null;
  await nextTick(); scene.value?.locate();
}
function setMode(value) { drawerBeforeSelection = null; mode.value = value; selected.value = null; search.value = ''; }
</script>

<template>
  <section class="map-page" aria-label="燕园活动探索">
    <div class="map-search-wrap">
      <label v-sketch class="map-search sketch"><AppIcon name="pin" /><input v-model="search" type="search" placeholder="找建筑、教室或活动…" aria-label="搜索燕园建筑、教室或活动" autocomplete="off" /><span class="search-campus">燕园</span></label>
      <div v-if="search.trim()" class="search-results" role="region" aria-label="本地搜索结果">
        <button v-for="building in results" :key="building.id" @click="select(building.id)"><AppIcon name="map" /><span>{{ building.name }}</span><span>↗</span></button>
        <p v-if="!results.length">没有找到，试试「理科」「208」或「电影」。</p>
      </div>
    </div>
    <div class="filter-row" aria-label="活动分类">
      <button v-for="item in filters" :key="item.id" v-sketch class="filter-chip sketch" :data-pencil="filter === item.id ? 'yellow' : undefined" :aria-pressed="filter === item.id" @click="filter = item.id">{{ item.label }}</button>
      <span class="demo-stamp">今日 · 演示</span>
    </div>
    <div class="map-stage" :class="{ 'empty-2d': mode === '2d', 'building-focus': selected }" :style="{ '--drawer-peek': `${mode === '3d' ? drawerPeek : 0}px` }">
      <CampusScene v-if="mode === '3d'" ref="scene" :focus-inset="drawerPeek" :selected="selected" :floor="floor" :activities="visibleActivities" @select="select" @floor="floor = $event" />
      <div v-else class="blank-map" aria-label="2D 地图留白，待后续设计"></div>
      <div class="mode-switch" aria-label="地图显示模式">
        <button v-for="item in ['3d', '2d']" :key="item" v-sketch class="sketch" :data-pencil="mode === item ? 'blue' : undefined" :aria-pressed="mode === item" @click="setMode(item)">{{ item.toUpperCase() }}</button>
      </div>
      <template v-if="mode === '3d'">
        <span class="campus-caption">北京大学 · 燕园</span>
        <div class="map-tools" aria-label="地图控制">
          <button v-sketch class="sketch" aria-label="放大地图" @click="scene?.zoom(.8)">＋</button>
          <button v-sketch class="sketch" aria-label="缩小地图" @click="scene?.zoom(1.25)">−</button>
          <button v-sketch class="sketch locate-button" :data-pencil="located ? 'blue' : undefined" aria-label="查看示例定位附近的活动" @click="locate">◎</button>
        </div>
        <div class="map-hint">{{ currentBuilding?.scenic ? '拖动环绕博雅塔 · 缩小看看未名湖' : selected ? '点楼层查看活动 · 拖动查看另一侧' : '点建筑，看看楼层里正在发生什么' }}</div>
        <a class="map-attribution" href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">© OpenStreetMap contributors</a>
      </template>
    </div>
    <ActivityDrawer v-if="mode === '3d'" ref="drawer" @measure="drawerPeek = $event">
      <template v-if="currentBuilding">
        <div class="sheet-heading"><div><p class="sheet-eyebrow">{{ currentBuilding.scenic ? 'LANDMARK / 燕园风景' : 'BUILDING / 楼层探索' }}</p><h2>{{ currentBuilding.short }}</h2></div><button v-sketch class="sketch collapse-button" @click="select(null)">{{ currentBuilding.scenic ? '返回地图 ↙' : '收起楼层 ↙' }}</button></div>
        <p v-if="currentBuilding.scenic" class="landmark-note">未名湖东南的十三重密檐塔。保留完整外观，拖动地图可环绕查看塔身与湖岸。<small>外观为实景特征的简化建模 · 此地标暂无示例活动</small></p>
        <template v-else>
        <p class="model-note">楼层 / 室内为示意 · 活动为固定演示数据</p>
        <div class="floor-picker" aria-label="选择建筑楼层">
          <button v-for="number in currentBuilding.floors" :key="number" v-sketch class="sketch" :data-pencil="floor === number ? 'blue' : undefined" :aria-pressed="floor === number" @click="floor = number">{{ number }}F<span v-if="visibleActivities.some(a => a.building === selected && a.floor === number)" class="floor-dot"></span></button>
        </div>
        <div class="floor-summary"><span>{{ floor }}F · {{ floorActivities.length ? `${floorActivities.length} 项课程 / 活动` : '暂无示例活动' }}</span><span>按教室查看</span></div>
        <button v-for="activity in floorActivities" :key="activity.id" v-sketch class="activity-card sketch" data-pencil="blue" @click="openActivity(activity)">
          <span class="room-tag">{{ activity.room }}<small>{{ activity.category }}</small></span><span class="activity-copy"><strong>{{ activity.title }}</strong><span>{{ activity.time }} · {{ activity.source }}</span></span><span class="card-arrow">↗</span>
        </button>
        <p v-if="!floorActivities.length" class="floor-empty">这一层先留一点空白，等新的校园故事。<br>可切换楼层或活动分类继续探索。</p>
        </template>
      </template>
      <template v-else>
        <div class="sheet-heading"><div><p class="sheet-eyebrow">NEARBY / 今天在燕园</p><h2>{{ located ? '示例位置附近' : '发现身边的小精彩' }}</h2></div><span class="activity-count">{{ visibleActivities.length }} 项</span></div>
        <p class="model-note">蓝点为示例位置 · 距离、课程与活动均非实时信息</p>
        <div class="venue-list" aria-label="选择建筑展开楼层"><button v-for="venue in venues" :key="venue.id" v-sketch class="sketch" @click="select(venue.id)">{{ venue.label }} ↗</button></div>
        <div class="today-cards">
          <button v-for="activity in today" :key="activity.id" v-sketch class="today-card sketch" :data-pencil="activity.type === 'culture' ? 'pink' : 'blue'" @click="select(activity.building); floor = activity.floor">
            <span class="today-top"><small>{{ activity.category }} · {{ activity.distance }}</small><span>↗</span></span><strong>{{ activity.title }}</strong><span>{{ activity.time }} · {{ venues.find(v => v.id === activity.building)?.label }} {{ activity.room }}</span><small>{{ activity.interest }}</small>
          </button>
        </div>
        <div v-sketch class="treehole-note sketch" data-pencil="mint"><span>附近树洞</span><p>“未名湖边的风刚刚好，读书会见！”<small>校园分享 · 固定消息示例</small></p></div>
      </template>
      <RouterLink v-sketch class="agent-entry sketch" data-pencil="yellow" to="/agent"><AppIcon name="agent" /><span>不知道去哪儿？问问校园 Agent</span><span>→</span></RouterLink>
    </ActivityDrawer>
    <dialog ref="dialog" class="map-activity-dialog" @click="event => { if (event.target === dialog) dialog.close(); }">
      <template v-if="detail"><div class="detail-heading"><span>{{ detail.category }} · 今日演示</span><button aria-label="关闭活动详情" @click="dialog.close()"><AppIcon name="close" /></button></div><h2>{{ detail.title }}</h2><p>{{ detail.time }}</p><p>{{ venues.find(v => v.id === detail.building)?.short }} · {{ detail.floor }}F · {{ detail.room }}</p><p class="detail-description">{{ detail.description }}</p><p class="detail-source">来源：{{ detail.source }}<br>固定演示内容，仅供界面设计参考。</p><button v-sketch class="sketch" data-pencil="yellow" @click="dialog.close(); select(detail.building); floor = detail.floor">返回楼层地图</button></template>
    </dialog>
  </section>
</template>

<style scoped>
.map-page { display: flex; flex: 1; flex-direction: column; min-width: 0; min-height: 0; }
.map-search-wrap { position: relative; margin: 0 17px; z-index: 8; }
.map-search { display: flex; align-items: center; gap: 7px; padding: 4px 12px; min-height: 44px; }
.map-search .icon { width: 18px; height: 18px; }
.map-search input { font: inherit; background: transparent; border: 0; color: var(--ink); width: 100%; min-width: 0; font-size: 12px; outline: none; padding: 6px 0; }
.map-search:focus-within { outline: 2px solid #82acd0; outline-offset: 2px; border-radius: 12px; }
.search-campus { font-size: 10px; white-space: nowrap; color: var(--muted); border-left: 1px solid #c8caca; padding-left: 9px; }
.search-results { position: absolute; top: calc(100% + 5px); left: 0; right: 0; padding: 6px 8px; background: #fffdf5; border: 1px solid #87939d; border-radius: 12px; box-shadow: 0 6px 20px #20304b20; }
.search-results button { display: flex; gap: 7px; width: 100%; padding: 12px 4px; align-items: center; background: transparent; border: 0; text-align: left; font-size: 12px; }
.search-results button span:last-child { margin-left: auto; }.search-results .icon { width: 15px; height: 15px; }.search-results p { font-size: 12px; }
.filter-row { display: flex; align-items: center; gap: 6px; padding: 8px 17px 10px; }
.filter-chip { padding: 7px 13px; min-height: 36px; font-size: 12px; background: transparent; }.demo-stamp { margin-left: auto; font-size: 10px; color: #899287; white-space: nowrap; }
.map-stage { position: relative; min-height: 0; flex: 1; overflow: hidden; background: var(--blue); border-top: 1px solid #20304b12; border-bottom: 1px solid #20304b16; }
.map-stage.empty-2d { flex: 1; background: transparent; }.blank-map { position: absolute; inset: 0; }
.mode-switch { position: absolute; right: 13px; top: 12px; display: flex; gap: 3px; padding: 3px; background: #faf9f2e6; border-radius: 12px; z-index: 4; }
.mode-switch button { min-width: 39px; min-height: 36px; padding: 6px 9px; font-size: 12px; background: transparent; }
.campus-caption { position: absolute; top: 17px; left: 15px; font-size: 11px; color: #6a7c78; pointer-events: none; }
.map-tools { position: absolute; right: 13px; top: 65px; display: grid; gap: 6px; z-index: 4; }
.map-tools button { width: 36px; height: 36px; padding: 0; font-size: 21px; background: transparent; }.map-tools .locate-button { margin-top: 5px; font-size: 23px; }
.map-hint { position: absolute; left: 15px; bottom: calc(var(--drawer-peek) + 24px); font-size: 10px; color: #526663; background: #f8f8efc4; padding: 4px 7px; border-radius: 6px; pointer-events: none; }
.map-attribution { position: absolute; right: 7px; bottom: calc(var(--drawer-peek) + 4px); font-size: 8px; color: #677570; background: #f8f8efb3; padding: 2px; }
.sheet-heading { display: flex; gap: 8px; align-items: center; justify-content: space-between; }.sheet-eyebrow { font-size: 9px; letter-spacing: .6px; color: #84928b; margin: 0 0 4px; }
h2 { font-size: 19px; line-height: 1.4; font-weight: 400; margin: 0; }.activity-count { font-size: 12px; color: #57766c; white-space: nowrap; }.model-note { font-size: 9px; line-height: 1.6; color: #8c968f; margin: 5px 0 9px; }
.venue-list { display: flex; gap: 5px; margin-bottom: 9px; }.venue-list button { padding: 5px 10px; background: transparent; font-size: 11px; min-height: 34px; flex: 1; }
.today-cards { display: flex; overflow-x: auto; gap: 9px; padding: 3px 2px 8px; scrollbar-width: thin; scroll-snap-type: x mandatory; }.today-card { display: flex; flex-direction: column; flex: 0 0 76%; gap: 6px; padding: 11px 13px; text-align: left; background: transparent; scroll-snap-align: start; }
.today-top { display: flex; justify-content: space-between; align-items: center; }.today-card strong { font-weight: 400; font-size: 16px; }.today-card > span:not(.today-top) { font-size: 11px; }.today-card small { font-size: 10px; color: #586f82; }
.treehole-note { display: flex; gap: 12px; padding: 11px 13px; margin-top: 7px; font-size: 11px; align-items: center; }.treehole-note > span { white-space: nowrap; font-size: 12px; }.treehole-note p { margin: 0; line-height: 1.6; }.treehole-note small { display: block; font-size: 9px; color: #71867a; }
.agent-entry { display: flex; align-items: center; gap: 8px; padding: 10px 12px; margin-top: 10px; font-size: 11px; min-height: 43px; }.agent-entry .icon { width: 20px; height: 20px; }.agent-entry > span:last-child { margin-left: auto; }
.collapse-button { background: transparent; font-size: 10px; padding: 7px 10px; min-height: 36px; white-space: nowrap; }
.landmark-note { font-size: 12px; line-height: 1.8; color: #657e6e; margin: 12px 0; }.landmark-note small { display: block; margin-top: 7px; font-size: 9px; color: #8c968f; }
.floor-picker { display: flex; gap: 7px; margin-top: 10px; }.floor-picker button { position: relative; min-width: 42px; min-height: 36px; background: transparent; padding: 7px 10px; font-size: 12px; }.floor-dot { width: 4px; height: 4px; border-radius: 50%; background: #3986ba; position: absolute; top: 7px; right: 7px; }
.floor-summary { display: flex; justify-content: space-between; color: #789089; font-size: 10px; margin: 13px 0 7px; }
.activity-card { display: flex; width: 100%; align-items: center; gap: 11px; padding: 12px; background: transparent; text-align: left; margin-top: 6px; }.room-tag { min-width: 35px; text-align: center; font-size: 17px; }.room-tag small { display: block; font-size: 9px; color: #5d788c; margin-top: 3px; }.activity-copy { display: grid; gap: 6px; }.activity-copy strong { font-weight: 400; font-size: 15px; }.activity-copy > span { font-size: 10px; color: #637b8d; }.card-arrow { margin-left: auto; }.floor-empty { text-align: center; padding: 16px 0; font-size: 12px; color: #8c9c95; line-height: 1.8; }
.map-activity-dialog { width: min(365px, calc(100% - 38px)); max-height: calc(100dvh - 70px); overflow: auto; border: 1.5px solid #657987; border-radius: 17px 15px 19px 14px; padding: 23px; color: var(--ink); background: #fbf8ef; }
.map-activity-dialog::backdrop { background: #20304b5c; backdrop-filter: blur(3px); }.detail-heading { display: flex; align-items: center; justify-content: space-between; font-size: 11px; color: #7e9186; }.detail-heading button { background: transparent; border: 0; width: 36px; height: 36px; }.detail-heading .icon { width: 20px; height: 20px; }.map-activity-dialog h2 { margin: 16px 0; font-size: 22px; }.map-activity-dialog p { font-size: 12px; line-height: 1.8; }.detail-description { margin: 20px 0; }.map-activity-dialog .detail-source { font-size: 10px; color: #88958b; }.map-activity-dialog > button { min-height: 42px; width: 100%; background: transparent; font-size: 12px; margin-top: 12px; }
@media (max-width: 359px) { .filter-row { gap: 3px; }.filter-chip { padding: 7px 10px; }.map-search-wrap { margin: 0 15px; }.activity-copy strong { font-size: 13px; }.activity-copy > span { font-size: 9px; }.floor-picker { gap: 4px; }.floor-picker button { min-width: 38px; } }
</style>
