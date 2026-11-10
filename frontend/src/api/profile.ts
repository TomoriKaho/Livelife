/**
 * 个人资料与兴趣标签请求：GET /profile/interests、GET /profile/me、PATCH /profile/me。
 * 服务端契约见 backend/app/api/profile/API.md；客户端行为见本目录 README.md。
 */
import { getApiBaseUrl } from '../platform/web';
import type { InterestTag, Profile } from '../types';

const ACCESS_TOKEN_KEY = 'livelife.access_token';
const REQUEST_TIMEOUT = 10_000;

/** 成功返回数据；失败返回可显示原因，status 用于区分未登录与其它错误。 */
export type ProfileResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: string; status?: number };

/** 读取本地会话令牌；“记住登录”写 localStorage，否则写 sessionStorage。 */
export function readAccessToken(): string | null {
  return window.localStorage.getItem(ACCESS_TOKEN_KEY) ?? window.sessionStorage.getItem(ACCESS_TOKEN_KEY);
}

/** 保存或清除本地会话令牌；令牌来自账户系统（#65）的登录响应。 */
export function writeAccessToken(token: string | null, remember = false): void {
  window.localStorage.removeItem(ACCESS_TOKEN_KEY);
  window.sessionStorage.removeItem(ACCESS_TOKEN_KEY);
  if (token) (remember ? window.localStorage : window.sessionStorage).setItem(ACCESS_TOKEN_KEY, token);
}

async function request<T>(
  path: string,
  init: RequestInit,
  token: string | null,
): Promise<ProfileResult<T>> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT);
  try {
    const baseUrl = getApiBaseUrl().replace(/\/+$/, '');
    const headers: Record<string, string> = {
      Accept: 'application/json',
      ...((init.headers as Record<string, string> | undefined) ?? {}),
    };
    if (token) headers.Authorization = `Bearer ${token}`;
    const resp = await fetch(`${baseUrl}${path}`, { ...init, headers, signal: controller.signal });
    if (resp.status === 401) return { ok: false, error: '登录状态已失效，请重新登录。', status: 401 };
    if (resp.status === 503) return { ok: false, error: '后端数据库未配置，资料暂时不可用。', status: 503 };
    if (resp.status === 400 || resp.status === 422) {
      return { ok: false, error: '提交的内容不符合要求，请检查昵称、简介和兴趣标签。', status: resp.status };
    }
    if (!resp.ok) return { ok: false, error: `后端返回 HTTP ${resp.status}。`, status: resp.status };
    return { ok: true, data: (await resp.json()) as T };
  } catch (error) {
    if (controller.signal.aborted) return { ok: false, error: '连接超时，请稍后重试。' };
    if (error instanceof SyntaxError) return { ok: false, error: '后端响应不是有效的 JSON。' };
    return { ok: false, error: '无法连接后端，请检查后端地址和服务状态。' };
  } finally {
    clearTimeout(timeout);
  }
}

/** 兴趣标签目录，无需登录。 */
export async function fetchInterestCatalog(): Promise<ProfileResult<InterestTag[]>> {
  return request<InterestTag[]>('/profile/interests', { method: 'GET' }, null);
}

/** 当前用户资料；无本地令牌时直接返回未登录，避免无意义请求。 */
export async function fetchProfile(): Promise<ProfileResult<Profile>> {
  const token = readAccessToken();
  if (!token) return { ok: false, error: '尚未登录，当前为界面预览。', status: 401 };
  return request<Profile>('/profile/me', { method: 'GET' }, token);
}

/** 只提交出现的字段；interests 为整体替换。 */
export interface ProfilePatch {
  display_name?: string;
  bio?: string;
  interests?: string[];
}

export async function updateProfile(patch: ProfilePatch): Promise<ProfileResult<Profile>> {
  const token = readAccessToken();
  if (!token) return { ok: false, error: '尚未登录，当前为界面预览。', status: 401 };
  return request<Profile>(
    '/profile/me',
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(patch),
    },
    token,
  );
}
