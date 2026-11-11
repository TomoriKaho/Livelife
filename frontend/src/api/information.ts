import type { CurrentLocation } from '../platform/location';
import { getApiBaseUrl } from '../platform/web';
import { checkAndroidStatus } from '../platform/android-config';
import { previewState } from '../platform/runtime-config';

export interface NearbyActivity {
  id: string;
  title: string | null;
  content: string;
  platform: string;
  source_name: string | null;
  source_url: string | null;
  activity_location: string | null;
  activity_start_at: string;
  activity_end_at: string | null;
  place: { id: string; name: string; building_id: string | null; latitude: number; longitude: number };
  location_resolution: { room: string | null; floor: string | null; precision: string | null } | null;
}

export async function fetchNearbyActivities(location: CurrentLocation, radius: number,
  keyword: string, today: boolean, signal: AbortSignal): Promise<NearbyActivity[]> {
  await checkAndroidStatus();
  const filters: Record<string, unknown> = { limit: 100 };
  if (keyword.trim()) filters.keyword = keyword.trim();
  if (today) {
    const date = new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Shanghai' }).format(new Date());
    const start = new Date(`${date}T00:00:00+08:00`);
    filters.activity_after = start.toISOString();
    filters.activity_before = new Date(start.getTime() + 86400000).toISOString();
  }
  const response = await fetch(`${getApiBaseUrl().replace(/\/+$/, '')}/events/nearby`, {
    method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({ location, radius_m: radius, filters }), signal,
  });
  if (previewState.enabled && previewState.config) {
    const sha = response.headers.get('X-Livelife-Backend-SHA');
    if (!sha || !/^[0-9a-f]{40}$/.test(sha)
      || (previewState.config.backend_mode !== 'staging' && sha !== previewState.config.backend_sha)) {
      throw new Error('后端版本与预览配置不一致，请检查联调配置。');
    }
  }
  if (response.status === 422) throw new Error('位置或查询参数已失效，请重新定位后重试。');
  if (!response.ok) throw new Error(`活动加载失败（${response.status}），请重试。`);
  const data: unknown = await response.json();
  if (!Array.isArray(data) || !data.every(row => row && typeof row.id === 'string'
    && typeof row.content === 'string' && typeof row.activity_start_at === 'string'
    && Number.isFinite(row.place?.latitude) && Number.isFinite(row.place?.longitude))) {
    throw new Error('活动数据格式异常，请重试。');
  }
  return data as NearbyActivity[];
}
