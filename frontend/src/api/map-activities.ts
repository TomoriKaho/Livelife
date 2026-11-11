import { checkAndroidStatus } from '../platform/android-config';
import { previewState } from '../platform/runtime-config';
import { getApiBaseUrl } from '../platform/web';

export interface MapActivity {
  id: string;
  title: string | null;
  summary: string;
  platform: string;
  source_url: string | null;
  location: string;
  start_at: string;
  end_at: string | null;
}

interface MapActivityPage {
  as_of: string;
  items: MapActivity[];
  next_offset: number | null;
}

function validActivity(item: unknown): item is MapActivity {
  if (!item || typeof item !== 'object') return false;
  const value = item as Record<string, unknown>;
  return typeof value.id === 'string' && typeof value.location === 'string'
    && typeof value.start_at === 'string' && !Number.isNaN(Date.parse(value.start_at))
    && (value.title === null || typeof value.title === 'string')
    && typeof value.summary === 'string' && typeof value.platform === 'string'
    && (value.source_url === null || (typeof value.source_url === 'string' && /^https?:\/\//i.test(value.source_url)))
    && (value.end_at === null || (typeof value.end_at === 'string' && !Number.isNaN(Date.parse(value.end_at))));
}

async function fetchPage(offset: number, asOf: string | null, signal: AbortSignal): Promise<MapActivityPage> {
  const controller = new AbortController();
  const abort = () => controller.abort();
  signal.addEventListener('abort', abort, { once: true });
  if (signal.aborted) controller.abort();
  const timeout = setTimeout(abort, 10_000);
  try {
    const params = new URLSearchParams({ limit: '100', offset: String(offset) });
    if (asOf) params.set('as_of', asOf);
    const base = getApiBaseUrl().replace(/\/+$/, '');
    const response = await fetch(`${base}/locations/activities?${params}`, {
      headers: { Accept: 'application/json' },
      signal: controller.signal,
    });
    const expected = previewState.enabled ? previewState.config : null;
    const sha = response.headers.get('X-Livelife-Backend-SHA');
    if (previewState.enabled && (!expected || !sha || !/^[0-9a-f]{40}$/.test(sha)
      || (expected.backend_mode !== 'staging' && sha !== expected.backend_sha))) {
      throw new Error('响应后端版本与测试配置不符，请刷新配置。');
    }
    if (response.status === 503) throw new Error('后端数据库尚未启用，附近活动暂不可用。');
    if (!response.ok) throw new Error(`附近活动查询失败（HTTP ${response.status}）。`);
    const data: unknown = await response.json();
    if (!data || typeof data !== 'object' || !('items' in data) || !Array.isArray(data.items)
      || !('as_of' in data) || typeof data.as_of !== 'string'
      || !data.items.every(validActivity)
      || !('next_offset' in data) || (data.next_offset !== null && (typeof data.next_offset !== 'number'
        || !Number.isInteger(data.next_offset) || data.next_offset < 0))) {
      throw new Error('附近活动响应格式不正确。');
    }
    return data as MapActivityPage;
  } catch (error) {
    if (signal.aborted) throw error;
    if (controller.signal.aborted) throw new Error('附近活动查询超时，请重试。');
    if (error instanceof Error && !/fetch failed|Failed to fetch|NetworkError/i.test(error.message)) throw error;
    throw new Error('无法连接后端，请检查网络与后端地址。');
  } finally {
    clearTimeout(timeout);
    signal.removeEventListener('abort', abort);
  }
}

export async function fetchMapActivities(signal: AbortSignal): Promise<MapActivity[]> {
  await checkAndroidStatus();
  if (previewState.enabled && !previewState.config) throw new Error(previewState.error || '测试配置不可用。');
  const items: MapActivity[] = [];
  let offset = 0, asOf: string | null = null;
  for (let page = 0; page < 100; page++) {
    const result = await fetchPage(offset, asOf, signal);
    asOf = result.as_of;
    items.push(...result.items);
    if (result.next_offset === null) return [...new Map(items.map(item => [item.id, item])).values()];
    if (result.next_offset <= offset) throw new Error('附近活动分页响应不正确。');
    offset = result.next_offset;
  }
  throw new Error('附近活动数量超过当前查询上限。');
}
