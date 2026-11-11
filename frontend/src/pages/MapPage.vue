<script>
export const pageMeta = { key: 'map', id: 'D-02', title: '活动地图', placeholder: '地图主页', label: 'MAP', eyebrow: 'EXPLORE THE CAMPUS', icon: 'map', accent: 'blue', nav: 'map', back: false, immersive: true, heading: false };
</script>

<script setup>
import { registerBackHandler } from '../platform/android-navigation';
import { computed, defineAsyncComponent, nextTick, onMounted, onBeforeUnmount, ref, watch } from 'vue';
import NearbyActivities from './map/NearbyActivities.vue';
import { useNearbyActivities } from './map/useNearbyActivities';
import AppIcon from '../components/AppIcon.vue';
import ActivityDrawer from './map/ActivityDrawer.vue';
import OsmAttribution from './map/OsmAttribution.vue';
import campus from '../assets/maps/campus.json';
import { isMapAttributionVisible } from './map/map-drawer-layout.mjs';
import { contains } from './map/geometry.mjs';
import { normalizeHeading, orientationHeading, orientationSensorHeading, preserveHeading, toDeviceMapLocation } from './map/device-location.mjs';
import { currentLocation, locationTrackingState, refreshCurrentLocation, restartLocationTracking } from '../platform/location-tracker';
import { watchAndroidDeviceHeading } from '../platform/device-heading';
const CampusScene = defineAsyncComponent(() => import('./map/CampusScene.vue'));
const CampusPlan = defineAsyncComponent(() => import('./map/CampusPlan.vue'));
const mode = ref('3d'), search = ref(''), selected = ref(null), floor = ref(2), scene = ref(null);
const deviceLocation = ref(null), outsideCampus = ref(false);
const drawer = ref(null), mapFocusInset = ref(180), drawerOcclusion = ref(180), drawerExpandedHeight = ref(540);
const mapAttributionVisible = computed(() => isMapAttributionVisible(drawerOcclusion.value, drawerExpandedHeight.value));
function onDrawerLayout({ occlusionHeight, expandedHeight }) {
  drawerOcclusion.value = occlusionHeight;
  drawerExpandedHeight.value = expandedHeight;
}
const planView = ref(null);
let drawerBeforeSelection = null, latestOrientation = null, latestNativeHeading = null, latestWebSensorHeading = null, deviceHeadingFrame = 0;
let stopNativeHeading = null, headingListenerGeneration = 0;
let centerAfterNextLocation = false;
let centeredOnDevice = false;
let webOrientationSensor = null;
const { items, radius, keyword, today, state: nearbyState, message: nearbyMessage, retry } = useNearbyActivities();
const visibleActivities = computed(() => items.value.map(item => ({
  id: item.id, building: item.place.building_id, room: item.location_resolution?.room,
  floor: null, title: item.title,
})));
const locationState = computed(() => outsideCampus.value ? 'outside-campus' : locationTrackingState.value);
const locationHint = computed(() => ({
  locating: '正在获取当前位置…',
  'permission-denied': '未获得位置权限；点击定位按钮可再次尝试。',
  unavailable: '暂时无法获取位置；请检查定位服务后重试。',
  timeout: '定位超时；点击定位按钮重试。',
  unsupported: '此设备暂不支持定位。',
  'outside-campus': '当前位置不在燕园离线地图范围内。',
}[locationState.value] || ''));
function screenAngle() {
  const angle = window.screen?.orientation?.angle;
  return Number.isFinite(angle) ? angle : 0;
}
function applyDeviceHeading() {
  if (!deviceLocation.value) return;
  // A web deviceorientation event has no synchronous "current value" API.
  // Keep north visible from the moment location is available, then replace it
  // on every live native/web sensor event.
  const heading = latestNativeHeading ?? latestWebSensorHeading ?? orientationHeading(latestOrientation, screenAngle()) ?? 0;
  const previous = deviceLocation.value.heading;
  if (previous === heading) return;
  deviceLocation.value = { ...deviceLocation.value, heading };
}
function scheduleDeviceHeading() {
  // 传感器可在一帧内给出多次读数；合并到下一次绘制，既不丢弃细微转向，也不重复重画地图。
  if (deviceHeadingFrame) return;
  deviceHeadingFrame = requestAnimationFrame(() => {
    deviceHeadingFrame = 0;
    applyDeviceHeading();
  });
}
function updateDeviceHeading(event) {
  latestOrientation = { alpha: event.alpha, webkitCompassHeading: event.webkitCompassHeading };
  scheduleDeviceHeading();
}
function updateNativeDeviceHeading(heading) {
  latestNativeHeading = normalizeHeading(heading);
  scheduleDeviceHeading();
}
function startAbsoluteWebHeadingSensor() {
  // The legacy DeviceOrientationEvent has no getter for a pre-existing value:
  // it only reports when the browser dispatches its next event. The Generic
  // Sensor API actively samples the current physical pose as soon as started.
  const Sensor = Reflect.get(window, 'AbsoluteOrientationSensor');
  if (typeof Sensor !== 'function') return;
  try {
    const sensor = new Sensor({ frequency: 60, referenceFrame: 'screen' });
    sensor.addEventListener('reading', () => {
      latestWebSensorHeading = orientationSensorHeading(sensor.quaternion);
      scheduleDeviceHeading();
    });
    sensor.addEventListener('error', () => { /* legacy deviceorientation remains the fallback */ });
    sensor.start();
    webOrientationSensor = sensor;
  } catch { /* unsupported, blocked, or unavailable sensor falls back below */ }
}
function startWebHeadingListener() {
  latestNativeHeading = latestWebSensorHeading = null;
  window.addEventListener('deviceorientationabsolute', updateDeviceHeading, true);
  window.addEventListener('deviceorientation', updateDeviceHeading, true);
  window.addEventListener('orientationchange', scheduleDeviceHeading, true);
  window.screen?.orientation?.addEventListener('change', scheduleDeviceHeading);
  startAbsoluteWebHeadingSensor();
  // Start immediately rather than waiting for the first physical rotation.
  scheduleDeviceHeading();
}
function stopWebHeadingListener() {
  window.removeEventListener('deviceorientationabsolute', updateDeviceHeading, true);
  window.removeEventListener('deviceorientation', updateDeviceHeading, true);
  window.removeEventListener('orientationchange', scheduleDeviceHeading, true);
  window.screen?.orientation?.removeEventListener('change', scheduleDeviceHeading);
  try { webOrientationSensor?.stop(); } catch { /* sensor may already be stopped */ }
  webOrientationSensor = null;
  latestWebSensorHeading = null;
}
async function startDeviceHeadingListener() {
  const generation = ++headingListenerGeneration;
  const stop = await watchAndroidDeviceHeading(updateNativeDeviceHeading);
  if (generation !== headingListenerGeneration) {
    await stop?.();
    return;
  }
  if (stop) {
    stopNativeHeading = stop;
    return;
  }
  startWebHeadingListener();
}
function stopDeviceHeadingListener() {
  headingListenerGeneration++;
  stopWebHeadingListener();
  const stop = stopNativeHeading;
  stopNativeHeading = null;
  latestNativeHeading = null;
  void stop?.();
}
async function requestDeviceHeadingPermission() {
  const orientationEvent = globalThis.DeviceOrientationEvent;
  const requestPermission = orientationEvent && Reflect.get(orientationEvent, 'requestPermission');
  if (typeof requestPermission !== 'function') return;
  try { await requestPermission.call(orientationEvent); } catch { /* requires an explicit user gesture on some browsers */ }
}
const results = computed(() => {
  const value = search.value.trim().toLowerCase();
  if (!value) return [];
  return campus.buildings.filter(b => b.name.toLowerCase().includes(value)
    || items.value.some(item => item.place.building_id === b.id
      && `${item.title || ''}${item.activity_location || ''}`.toLowerCase().includes(value))).slice(0, 6);
});
const removeBackHandler = registerBackHandler(() => {
  if (selected.value) { select(null); return true; }
  if (search.value) { search.value = ''; return true; }
  return false;
});
onBeforeUnmount(() => {
  removeBackHandler();
  cancelAnimationFrame(deviceHeadingFrame);
  stopDeviceHeadingListener();
});
function select(id) {
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
function syncDeviceLocation(location) {
  if (!location) return;
  const nextLocation = toDeviceMapLocation(location);
  if (!nextLocation || !contains(nextLocation.point, campus.boundary)) {
    deviceLocation.value = null;
    outsideCampus.value = true;
    return;
  }
  outsideCampus.value = false;
  deviceLocation.value = preserveHeading(nextLocation, deviceLocation.value?.heading);
  applyDeviceHeading();
  if (centerAfterNextLocation || !centeredOnDevice) {
    centerAfterNextLocation = false;
    void centerOnDeviceLocation();
  }
}
async function centerOnDeviceLocation() {
  const point = deviceLocation.value?.point;
  if (!point || !scene.value) return false;
  centeredOnDevice = true;
  // Explicitly locating exits exploration and restores each map's fixed
  // location view: CampusPlan resets scale and CampusScene resets its camera
  // offset, rather than merely moving the existing viewport.
  drawerBeforeSelection = null; selected.value = null;
  await nextTick();
  scene.value?.locate(point);
  return true;
}
async function locate({ requestHeading = false } = {}) {
  if (locationState.value === 'locating') return;
  if (requestHeading) await requestDeviceHeadingPermission();
  // The last foreground fix is already suitable for an immediate, predictable
  // re-center. A browser's fresh getCurrentPosition call can legitimately take
  // up to its timeout, so it must not make the control look unresponsive.
  await centerOnDeviceLocation();
  if (locationTrackingState.value !== 'located' || !deviceLocation.value) {
    // A retry may replace an old marker too; re-center once its next usable
    // callback arrives even if we could immediately show the previous fix.
    centerAfterNextLocation = true;
    await restartLocationTracking();
    return;
  }
  // A location button must not deliberately re-center on an old watcher value.
  // The shared watch continues in the background; this one-shot request is only
  // for this explicit user action.
  const refreshed = await refreshCurrentLocation();
  if (refreshed.status === 'success') await centerOnDeviceLocation();
}
async function setMode(value) {
  if (value === mode.value) return;
  if (mode.value === '2d') planView.value = scene.value?.getView();
  // 两种地图共用建筑、楼层和抽屉状态，切换后继续查看同一处活动。
  mode.value = value; search.value = '';
  await nextTick();
}
onMounted(() => { void startDeviceHeadingListener(); });
watch(currentLocation, syncDeviceLocation, { immediate: true });
watch(scene, value => { if (value && !centeredOnDevice) void centerOnDeviceLocation(); });
</script>

<template>
  <section id="page-title" class="map-page" aria-label="燕园活动探索" tabindex="-1">
    <div class="map-rule" aria-hidden="true"></div>
    <div class="map-stage" :class="{ 'building-focus': selected, 'plan-mode': mode === '2d' }" :style="{ '--drawer-occlusion': `${drawerOcclusion}px` }">
        <CampusScene v-if="mode === '3d'" ref="scene" :focus-inset="mapFocusInset" :device-location="deviceLocation" :selected="selected" :floor="floor" :activities="visibleActivities" @select="select" @floor="floor = $event" />
        <CampusPlan v-else ref="scene" :focus-inset="mapFocusInset" :device-location="deviceLocation" :selected="selected" :activities="visibleActivities" :starting-view="planView" @select="select" />
        <span v-if="mode === '3d'" class="campus-caption">北京大学 · 燕园</span>
        <div class="map-hint">{{ selected ? "建筑布局为示意 · 活动地点见下方列表" : "点建筑查看活动 · 拖动与缩放地图" }}</div>
      <OsmAttribution v-if="mapAttributionVisible" class="map-attribution" />
      <div class="map-overlay">
      <div class="map-search-wrap">
        <label v-sketch class="map-search sketch sketch-white"><AppIcon name="pin" /><input v-model="search" type="search" placeholder="找建筑、教室或活动…" aria-label="搜索燕园建筑、教室或活动" autocomplete="off" /><span class="search-campus">燕园</span></label>
        <div v-if="search.trim()" class="search-results" role="region" aria-label="本地搜索结果">
          <button v-for="building in results" :key="building.id" @click="select(building.id)"><AppIcon name="map" /><span>{{ building.name }}</span><span>↗</span></button>
          <p v-if="!results.length">没有找到，试试「理科」「208」或「电影」。</p>
        </div>
      </div>
      <div class="filter-row"><span class="demo-stamp">设备定位 · 后端活动 · 建筑级地点</span></div>
      </div>
      <div class="map-rail">
        <div v-sketch class="mode-switch sketch sketch-white sketch-cast" data-cast="blue" role="tablist" aria-label="地图显示模式">
          <button v-for="item in ['3d', '2d']" :key="`${item}-${mode === item}`" v-sketch class="mode-tab" :class="mode === item ? 'sketch pencil-fill sketch-fill-only' : ''" :data-pencil="mode === item ? 'blue' : undefined" type="button" role="tab" :aria-selected="mode === item" @click="setMode(item)">{{ item.toUpperCase() }}</button>
        </div>
        <div class="map-tools" aria-label="地图控制">
          <button v-sketch class="sketch" aria-label="放大地图" @click="scene?.zoom(.8)">＋</button>
          <button v-sketch class="sketch" aria-label="缩小地图" @click="scene?.zoom(1.25)">−</button>
          <button v-sketch class="sketch locate-button" :aria-label="locationState === 'locating' ? '正在定位' : '定位到我的位置'" :disabled="locationState === 'locating'" @click="locate({ requestHeading: true })">◎</button>
        </div>
      </div>
      <p v-if="locationHint" class="location-hint" :class="{ error: locationState !== 'locating' }" :role="locationState === 'locating' ? 'status' : 'alert'">{{ locationHint }}</p>
    </div>
    <ActivityDrawer ref="drawer" @measure="mapFocusInset = $event" @layout="onDrawerLayout">
      <NearbyActivities v-model:radius="radius" v-model:keyword="keyword" v-model:today="today"
        :items="items" :state="nearbyState" :message="nearbyMessage" :selected="selected"
        @select="select" @retry="retry" />
    </ActivityDrawer>
  </section>
</template>

<style scoped>
.map-page { position: relative; display: flex; flex: 1; flex-direction: column; min-width: 0; min-height: 0; outline: none; }
.map-rule { height: 1.5px; flex: 0 0 auto; background: #20304b; }
/* 右下角跟随当前抽屉遮挡高度 --drawer-occlusion，避开搜索框与控件；全展开时隐藏署名。 */
.map-attribution { position: absolute; right: 8px; bottom: calc(var(--drawer-occlusion) + 8px); z-index: 12; }
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
.location-hint { position: absolute; z-index: 7; left: 14px; right: 72px; bottom: calc(var(--drawer-occlusion) + 14px); margin: 0; padding: 7px 10px; border-radius: 8px; background: #fffdf0e8; color: #315974; font-size: 11px; line-height: 1.35; box-shadow: 0 1px 0 #20304b33; pointer-events: none; }.location-hint.error { color: #805049; }
.map-rail { position: absolute; right: 12px; top: 104px; z-index: 6; display: flex; flex-direction: column; align-items: center; gap: 8px; }
.mode-switch { display: grid; grid-template-columns: 1fr; width: 44px; padding: 3px; background: transparent; }
.mode-tab { min-height: 34px; border: 0; background: transparent; font-size: 11px; color: var(--ink); padding: 4px 0; }
.campus-caption { position: absolute; top: 108px; left: 15px; font-size: 11px; color: #6a7c78; pointer-events: none; }
.map-tools { display: grid; gap: 6px; }
.map-tools button { width: 36px; height: 36px; padding: 0; font-size: 21px; background: transparent; }.map-tools .locate-button { font-size: 23px; }
.map-hint { position: absolute; left: 15px; bottom: calc(var(--drawer-occlusion) + 24px); font-size: 10px; color: #526663; background: #f8f8efc4; padding: 4px 7px; border-radius: 6px; pointer-events: none; }
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
.intro-head { display: flex; align-items: center; gap: 2px; min-height: 36px; }
.intro-pill { justify-self: start; display: inline-flex; align-items: center; gap: 6px; min-height: 28px; padding: 2px 10px; background: transparent; font-size: 13px; }
.intro-pill i { width: 8px; height: 8px; border-radius: 50%; }
.intro-title-row { display: flex; align-items: flex-start; gap: 8px; margin-top: -8px; }
.intro-actions { display: flex; align-items: center; gap: 2px; flex: none; margin-left: auto; }
.intro-back { display: grid; place-items: center; width: 36px; height: 36px; flex: none; border: 0; background: transparent; padding: 6px; color: var(--ink); }
.intro-back .icon { width: 22px; height: 22px; }
.intro-view { position: relative; display: grid; place-items: center; width: 42px; height: 42px; flex: none; border: 0; background: transparent; padding: 6px; color: var(--ink); text-decoration: none; }
.intro-view .icon { position: relative; z-index: 1; width: 28px; height: 28px; }
.eye-pencil { position: absolute; left: 50%; top: 50%; width: 224px; height: 224px; margin: -112px 0 0 -112px; border: 0; transform: scale(.125); pointer-events: none; clip-path: ellipse(39% 31% at 50% 50%); }
.intro-save { position: relative; display: grid; place-items: center; width: 42px; height: 42px; border: 0; background: transparent; padding: 6px; }
.bookmark-pencil { position: absolute; left: 50%; top: 50%; width: 176px; height: 240px; margin: -120px 0 0 -88px; border: 0; transform: scale(.125); pointer-events: none; clip-path: polygon(16.7% 7.8%, 83.3% 7.8%, 83.3% 89.1%, 50% 70.3%, 16.7% 89.1%); }
.intro-save svg { position: relative; z-index: 1; width: 22px; height: 30px; fill: transparent; stroke: var(--ink); stroke-width: 1.8; stroke-linejoin: round; }
.intro-name { width: max-content; max-width: calc(100% - 92px); margin: 0; padding: 10px 14px; font-size: 28px; font-weight: 400; line-height: 1.2; background: transparent; }
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
