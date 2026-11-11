import { checkAndroidStatus } from '../platform/android-config';
import { previewState } from '../platform/runtime-config';
import { getApiBaseUrl } from '../platform/web';
import type { CurrentLocation } from '../platform/location';

interface Place { id: string; name: string; building_id: string | null; latitude: number; longitude: number }
export interface CalendarActivity {
  id: string; title: string | null; summary: string; platform: string; source_name: string | null;
  source_url: string | null; location: string; start_at: string; end_at: string | null;
  place: Place; location_resolution: { room: string | null; floor: string | null } | null;
  distance_m: number | null;
}
export interface MapActivity extends CalendarActivity {
  distance_m: number; building: string | null; distance: number;
}
export interface MapBuilding { id: string; name: string; distance: number }
interface Page { as_of: string; window_end: string; items: CalendarActivity[]; nearby_buildings: { place: Place; distance_m: number }[]; next_offset: number | null }
function validPlace(value: Place) { return value && typeof value.id === 'string' && typeof value.name === 'string' && (value.building_id === null || typeof value.building_id === 'string') && Number.isFinite(value.latitude) && Number.isFinite(value.longitude); }
function validActivity(item: CalendarActivity) {
  return item && typeof item.id === 'string' && typeof item.location === 'string' && typeof item.summary === 'string'
    && typeof item.platform === 'string' && (item.title === null || typeof item.title === 'string')
    && Number.isFinite(Date.parse(item.start_at)) && (item.end_at === null || Number.isFinite(Date.parse(item.end_at)))
    && (item.source_url === null || (typeof item.source_url === 'string' && /^https?:\/\//i.test(item.source_url)))
    && validPlace(item.place) && (item.distance_m === null || (Number.isFinite(item.distance_m) && item.distance_m >= 0));
}
export async function fetchMapActivities(location: CurrentLocation, radius: number, keyword: string, today: boolean, signal: AbortSignal) {
  const params = new URLSearchParams({ latitude: String(location.latitude), longitude: String(location.longitude), timestamp: String(location.timestamp), radius_m: String(radius), limit: '100' });
  if (keyword.trim()) params.set('keyword', keyword.trim());
  if (today) {
    const date = new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Shanghai' }).format(new Date());
    params.set('activity_before', new Date(new Date(`${date}T00:00:00+08:00`).getTime() + 86400000).toISOString());
  }
  const result = await fetchActivityPages(params, signal);
  if (result.items.some(item => item.distance_m === null)) throw new Error('附近活动缺少距离。');
  return { ...result, items: result.items.map(item => ({ ...item, distance_m: item.distance_m!, building: item.place.building_id, distance: item.distance_m! })) };
}

export async function fetchCalendarActivities(start: string, end: string, signal: AbortSignal) {
  return fetchActivityPages(new URLSearchParams({ as_of: start, activity_before: end, limit: '100' }), signal);
}

async function fetchActivityPages(params: URLSearchParams, signal: AbortSignal) {
  await checkAndroidStatus();
  if (previewState.enabled && !previewState.config) throw new Error(previewState.error || '测试配置不可用。');
  const items: CalendarActivity[] = []; let buildings: MapBuilding[] = []; let offset = 0;
  for (let page = 0; page < 100; page++) {
    params.set('offset', String(offset));
    const response = await fetch(`${getApiBaseUrl().replace(/\/+$/, '')}/locations/activities?${params}`, { headers: { Accept: 'application/json' }, signal });
    const expected = previewState.enabled ? previewState.config : null;
    const sha = response.headers.get('X-Livelife-Backend-SHA');
    if (previewState.enabled && (!expected || !sha || !/^[0-9a-f]{40}$/.test(sha) || (expected.backend_mode !== 'staging' && sha !== expected.backend_sha))) throw new Error('响应后端版本与测试配置不符，请刷新配置。');
    if (response.status === 503) throw new Error('后端数据库尚未启用，活动暂不可用。');
    if (response.status === 422) throw new Error('位置或查询参数已失效，请重新定位后重试。');
    if (!response.ok) throw new Error(`附近活动查询失败（HTTP ${response.status}）。`);
    const data: Page = await response.json();
    if (!data || !Array.isArray(data.items) || !data.items.every(validActivity)
      || !Number.isFinite(Date.parse(data.as_of)) || !Number.isFinite(Date.parse(data.window_end))
      || !Array.isArray(data.nearby_buildings) || !data.nearby_buildings.every(b => validPlace(b.place) && typeof b.place.building_id === 'string' && Number.isFinite(b.distance_m))
      || (data.next_offset !== null && (!Number.isInteger(data.next_offset) || data.next_offset <= offset))) throw new Error('附近活动响应格式不正确。');
    if (page === 0) {
      params.set('as_of', data.as_of); params.set('activity_before', data.window_end);
      buildings = data.nearby_buildings.map(b => ({ id: b.place.building_id!, name: b.place.name, distance: b.distance_m }));
    }
    items.push(...data.items);
    if (data.next_offset === null) return { items: [...new Map(items.map(item => [item.id, item])).values()], buildings };
    offset = data.next_offset;
  }
  throw new Error('附近活动数量超过当前查询上限，请缩小范围。');
}
