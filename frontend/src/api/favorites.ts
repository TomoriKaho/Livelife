import { readAuthToken, clearSession } from './auth';
import { checkAndroidStatus } from '../platform/android-config';
import { previewState } from '../platform/runtime-config';
import { getApiBaseUrl } from '../platform/web';

export type FavoriteStatus = 'upcoming' | 'ongoing' | 'ended' | 'unknown';
export interface FavoriteItem {
  id: string; saved_at: string; available: boolean; title: string | null;
  platform: string; source_name: string | null; source_url: string | null;
  activity_date: string | null; start_at: string | null; end_at: string | null;
  location: string | null;
  place: { id: string; name: string; building_id: string | null; latitude: number; longitude: number } | null;
  status: FavoriteStatus;
}
export interface FavoritePage {
  items: FavoriteItem[]; as_of: string; counts: Record<FavoriteStatus, number>;
  total: number; next_offset: number | null;
}
const statuses = ['upcoming', 'ongoing', 'ended', 'unknown'];
export const isInformationId = (id: string) => /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id);
function validItem(item: FavoriteItem) {
  return item && isInformationId(item.id) && typeof item.available === 'boolean'
    && Number.isFinite(Date.parse(item.saved_at)) && statuses.includes(item.status)
    && (item.title === null || typeof item.title === 'string') && typeof item.platform === 'string'
    && (item.location === null || typeof item.location === 'string')
    && (item.source_name === null || typeof item.source_name === 'string')
    && (item.source_url === null || (typeof item.source_url === 'string' && /^https?:\/\//i.test(item.source_url)))
    && [item.start_at, item.end_at].every(v => v === null || (typeof v === 'string' && Number.isFinite(Date.parse(v))))
    && (item.activity_date === null || /^\d{4}-\d{2}-\d{2}$/.test(item.activity_date))
    && (item.place === null || (typeof item.place.id === 'string' && typeof item.place.name === 'string'
      && (item.place.building_id === null || typeof item.place.building_id === 'string')
      && Number.isFinite(item.place.latitude) && Number.isFinite(item.place.longitude)));
}
async function request(path: string, method = 'GET', body?: unknown): Promise<unknown> {
  const token = readAuthToken();
  if (!token) throw new Error('请先登录后使用收藏。');
  await checkAndroidStatus();
  if (token !== readAuthToken()) throw new Error('登录状态已变更，请重试。');
  if (previewState.enabled && !previewState.config) throw new Error(previewState.error || '测试配置不可用。');
  let response: Response;
  try {
    response = await fetch(`${getApiBaseUrl().replace(/\/+$/, '')}/favorites/activities${path}`, {
      method, headers: { Accept: 'application/json', Authorization: `Bearer ${token}`, ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) },
      body: body === undefined ? undefined : JSON.stringify(body), signal: AbortSignal.timeout(10_000),
    });
  } catch { throw new Error('收藏请求未完成，请检查网络后重试；可重新加载确认保存结果。'); }
  if (token !== readAuthToken()) throw new Error('登录状态已变更，请重试。');
  const expected = previewState.enabled ? previewState.config : null;
  const sha = response.headers.get('X-Livelife-Backend-SHA');
  if (previewState.enabled && (!expected || !sha || !/^[0-9a-f]{40}$/.test(sha)
    || (expected.backend_mode !== 'staging' && expected.backend_sha !== sha))) throw new Error('响应后端版本与测试配置不符，请刷新配置。');
  if (response.status === 401) { clearSession(); throw new Error('登录已过期，请重新登录。'); }
  if (response.status === 404) throw new Error('活动或收藏已不可用，请重新加载。');
  if (response.status === 503) throw new Error('收藏服务暂不可用，请稍后重试。');
  if (!response.ok) throw new Error(`收藏请求失败（HTTP ${response.status}），请重试。`);
  if (response.status === 204) return undefined;
  return response.json();
}
export async function favoriteMembership(ids: string[]) {
  const result = await request('/status', 'POST', { ids }) as { saved_ids: string[] };
  if (!result || !Array.isArray(result.saved_ids) || !result.saved_ids.every(id => ids.includes(id))) throw new Error('收藏状态响应格式不正确。');
  return result.saved_ids;
}
export async function favoritePage(status: FavoriteStatus, offset = 0, asOf?: string) {
  const query = new URLSearchParams({ status, limit: '20', offset: String(offset) });
  if (asOf) query.set('as_of', asOf);
  const result = await request(`?${query}`) as FavoritePage;
  if (!result || !Array.isArray(result.items) || !result.items.every(validItem)
    || !Number.isFinite(Date.parse(result.as_of)) || !Number.isInteger(result.total) || result.total < 0
    || !result.counts || !statuses.every(s => Number.isInteger(result.counts[s as FavoriteStatus]) && result.counts[s as FavoriteStatus] >= 0)
    || (result.next_offset !== null && (!Number.isInteger(result.next_offset) || result.next_offset <= offset))) throw new Error('收藏列表响应格式不正确。');
  return result;
}
export async function favoriteDetail(id: string) {
  const result = await request(`/${id}`) as FavoriteItem;
  if (!validItem(result) || result.id !== id) throw new Error('收藏响应格式不正确。');
  return result;
}
export async function setFavorite(id: string, saved: boolean) {
  const result = await request(`/${id}`, saved ? 'PUT' : 'DELETE');
  if (saved && (!validItem(result as FavoriteItem) || (result as FavoriteItem).id !== id)) throw new Error('收藏响应格式不正确，请重新加载确认。');
}
