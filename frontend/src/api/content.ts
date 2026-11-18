import { checkAndroidStatus } from '../platform/android-config';
import { previewState } from '../platform/runtime-config';
import { getApiBaseUrl } from '../platform/web';

export interface ContentArticle {
  id: string; title: string | null; excerpt: string; platform: string;
  source_name: string | null; source_url: string | null;
  published_at: string | null; fetched_at: string;
}
export interface ContentPage { items: ContentArticle[]; next_offset: number | null }
export interface ContentFilters { keyword: string; platform: string; source_name: string }

export function safeSourceUrl(value: unknown): value is string {
  if (typeof value !== 'string') return false;
  try { const url = new URL(value); return ['http:', 'https:'].includes(url.protocol) && !url.username && !url.password; }
  catch { return false; }
}
export async function fetchContent(filters: ContentFilters, offset: number, signal: AbortSignal): Promise<ContentPage> {
  await checkAndroidStatus();
  signal.throwIfAborted();
  if (previewState.enabled && !previewState.config) throw new Error(previewState.error || '测试配置不可用。');
  const params = new URLSearchParams({ offset: String(offset), limit: '20' });
  for (const [key, value] of Object.entries(filters)) if (value.trim()) params.set(key, value.trim());
  const response = await fetch(`${getApiBaseUrl().replace(/\/+$/, '')}/content/articles?${params}`, { headers: { Accept: 'application/json' }, signal });
  const expected = previewState.enabled ? previewState.config : null;
  const sha = response.headers.get('X-Livelife-Backend-SHA');
  if (previewState.enabled && (!expected || !sha || !/^[0-9a-f]{40}$/.test(sha) || (expected.backend_mode !== 'staging' && sha !== expected.backend_sha))) throw new Error('响应后端版本与测试配置不符，请刷新配置。');
  if (response.status === 503) throw new Error('后端数据库尚未启用，内容暂不可用。');
  if (response.status === 422) throw new Error('查询条件不符合要求，请检查平台标识与输入长度。');
  if (!response.ok) throw new Error(`内容读取失败（HTTP ${response.status}）。`);
  const data: ContentPage = await response.json();
  if (!data || !Array.isArray(data.items) || !data.items.every(item => item
    && typeof item.id === 'string' && typeof item.excerpt === 'string' && typeof item.platform === 'string'
    && (item.title === null || typeof item.title === 'string')
    && (item.source_name === null || typeof item.source_name === 'string')
    && (item.source_url === null || safeSourceUrl(item.source_url))
    && Number.isFinite(Date.parse(item.fetched_at))
    && (item.published_at === null || Number.isFinite(Date.parse(item.published_at))))
    || (data.next_offset !== null && (!Number.isInteger(data.next_offset) || data.next_offset <= offset))) throw new Error('内容响应格式不正确。');
  return data;
}
