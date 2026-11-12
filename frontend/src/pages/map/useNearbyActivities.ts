import { onBeforeUnmount, ref, watch } from 'vue';
import { fetchMapActivities, type MapActivity, type MapBuilding } from '../../api/map-activities';
import { currentLocation, locationTrackingState, refreshCurrentLocation } from '../../platform/location-tracker';
import type { CurrentLocation } from '../../platform/location';

export function distanceMeters(a: { latitude: number; longitude: number }, b: { latitude: number; longitude: number }) {
  const radians = Math.PI / 180;
  const h = Math.sin((b.latitude - a.latitude) * radians / 2) ** 2
    + Math.cos(a.latitude * radians) * Math.cos(b.latitude * radians)
    * Math.sin((b.longitude - a.longitude) * radians / 2) ** 2;
  return 6371008.8 * 2 * Math.asin(Math.sqrt(Math.min(1, h)));
}

export function useNearbyActivities() {
  const items = ref<MapActivity[]>([]);
  const buildings = ref<MapBuilding[]>([]);
  const radius = ref(300), keyword = ref(''), today = ref(false);
  const state = ref('waiting'), message = ref('允许定位后查看附近活动。');
  let controller: AbortController | null = null;
  let timer: ReturnType<typeof setTimeout> | undefined;
  let generation = 0, lastRequestedAt = 0;
  let lastPosition: CurrentLocation | null = null;
  let alive = true;

  function unavailable() {
    if (locationTrackingState.value !== 'located') {
      return locationTrackingState.value === 'permission-denied' ? '未获得位置权限，请允许定位后重试。' : '等待有效定位，请检查设备定位服务。';
    }
    const age = Date.now() - (currentLocation.value?.timestamp ?? 0);
    return age > 120000 || age < -10000 ? '位置已过期，请重新定位后重试。' : '';
  }
  function invalidate() {
    generation++;
    controller?.abort();
    clearTimeout(timer);
    items.value = []; buildings.value = [];
  }
  async function load() {
    const issue = unavailable();
    if (issue || !currentLocation.value) {
      invalidate(); state.value = 'waiting'; message.value = issue; return;
    }
    invalidate();
    const requestGeneration = generation;
    const position = { ...currentLocation.value };
    const active = new AbortController();
    controller = active;
    lastPosition = position; lastRequestedAt = Date.now();
    state.value = 'loading'; message.value = '正在查找附近活动…';
    const timeout = setTimeout(() => active.abort(), 10000);
    try {
      const result = await fetchMapActivities(position, radius.value, keyword.value, today.value, active.signal);
      if (!alive || requestGeneration !== generation) return;
      items.value = result.items; buildings.value = result.buildings;
      state.value = 'ready';
      message.value = result.items.length ? `找到 ${result.items.length} 条活动` : '当前范围和筛选条件下暂无活动。';
    } catch (error) {
      if (!alive || requestGeneration !== generation) return;
      state.value = 'error';
      message.value = active.signal.aborted ? '请求超时，请重试。'
        : error instanceof Error ? error.message : '暂时无法加载活动，请重试。';
    } finally { clearTimeout(timeout); }
  }
  function locationChanged() {
    const issue = unavailable();
    if (issue) { invalidate(); state.value = 'waiting'; message.value = issue; return; }
    const position = currentLocation.value!;
    if (!lastPosition || state.value === 'waiting' || distanceMeters(lastPosition, position) >= 25
      || Date.now() - lastRequestedAt >= 30000) void load();
  }
  watch([currentLocation, locationTrackingState], locationChanged, { immediate: true });
  watch([radius, keyword, today], () => {
    invalidate(); state.value = 'loading'; message.value = '正在更新筛选…';
    timer = setTimeout(() => void load(), 350);
  });
  let refreshedAt = Date.now();
  const expiry = setInterval(() => {
    if (state.value !== 'waiting' && unavailable()) locationChanged();
    else if (state.value === 'ready' && Date.now() - refreshedAt >= 60000) { refreshedAt = Date.now(); void load(); }
  }, 1000);
  async function retry() {
    await refreshCurrentLocation();
    if (alive) await load();
  }
  onBeforeUnmount(() => { alive = false; invalidate(); clearInterval(expiry); });
  return { items, buildings, radius, keyword, today, state, message, retry };
}
