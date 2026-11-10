import { reactive } from 'vue';
import { checkAndroidStatus } from '../platform/android-config';
import { previewState } from '../platform/runtime-config';
import { getApiBaseUrl } from '../platform/web';

export interface AuthUser {
  id: string;
  email: string;
}

interface AuthSession {
  access_token: string;
  token_type: 'bearer';
  expires_in: number;
  user: AuthUser;
}

export const authState = reactive<{ user: AuthUser | null }>({ user: null });

/** 读取本地会话令牌；账户与个人资料模块共用同一存储键。 */
export function readAuthToken(): string | null {
  return localStorage.getItem('livelife.auth.token') || sessionStorage.getItem('livelife.auth.token');
}

/** 保存或清除本地会话令牌；“记住登录”写 localStorage，否则写 sessionStorage。 */
export function writeAuthToken(token: string | null, remember = false): void {
  localStorage.removeItem('livelife.auth.token');
  sessionStorage.removeItem('livelife.auth.token');
  if (token) (remember ? localStorage : sessionStorage).setItem('livelife.auth.token', token);
}

function readToken(): string | null {
  return readAuthToken();
}

function saveSession(data: AuthSession, remember: boolean): void {
  clearSession();
  const storage = remember ? localStorage : sessionStorage;
  storage.setItem('livelife.auth.token', data.access_token);
  authState.user = data.user;
}

export function clearSession(): void {
  localStorage.removeItem('livelife.auth.token');
  sessionStorage.removeItem('livelife.auth.token');
  authState.user = null;
}

async function request<T>(path: string, body?: unknown, authenticated = false): Promise<T> {
  await checkAndroidStatus();
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  const token = authenticated ? readToken() : null;
  if (token) headers.Authorization = `Bearer ${token}`;
  const apiUrl = `${getApiBaseUrl().replace(/\/+$/, '')}${path}`;
  let response: Response;
  try {
    response = await fetch(apiUrl, {
      method: body === undefined ? 'GET' : 'POST',
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(15_000),
    });
  } catch (error) {
    if (error instanceof Error && (error.name === 'AbortError' || error.name === 'TimeoutError')) {
      throw new Error('请求超时，请稍后重试。');
    }
    throw new Error('无法连接后端，请检查 API 地址和服务状态。');
  }
  const responseSha = response.headers.get('X-Livelife-Backend-SHA');
  if (previewState.enabled && previewState.config && (
    responseSha === null
    || !/^[0-9a-f]{40}$/.test(responseSha)
    || (previewState.config.backend_mode !== 'staging' && responseSha !== previewState.config.backend_sha)
  )) {
    throw new Error('响应后端版本与测试配置不符，请刷新配置并检查部署状态。');
  }
  if (response.status === 204) return undefined as T;
  const data: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(authError(data, response.status, path));
  }
  return data as T;
}

function authError(data: unknown, status: number, path: string): string {
  if (status === 403 && typeof data === 'object' && data !== null && 'detail' in data
    && data.detail === 'Test login is disabled') return '临时测试登录未启用，请填写校园邮箱和密码。';
  if (status === 400) return '验证码错误或已过期，请重新获取。';
  if (status === 401) return '邮箱或密码错误，或登录状态已失效。';
  if (status === 409) return '该邮箱已注册，请直接登录。';
  if (status === 503) return '账号服务暂不可用，请检查数据库或邮件服务配置。';
  if (typeof data === 'object' && data !== null && 'detail' in data && Array.isArray(data.detail)) {
    const error = data.detail[0];
    const location = typeof error === 'object' && error !== null && 'loc' in error && Array.isArray(error.loc)
      ? error.loc.at(-1) : undefined;
    if (location === 'email') return '请输入有效的北大校园邮箱地址。';
    if (location === 'code') return '请输入 6 位邮箱验证码。';
    if (location === 'password') {
      return path.endsWith('/register') ? '密码长度需为 10–128 位。' : '密码不能超过 128 位。';
    }
    return '请检查填写内容后重试。';
  }
  return `请求失败（HTTP ${status}），请稍后重试。`;
}

export async function sendEmailCode(email: string): Promise<void> {
  await request('/auth/email-codes', { email });
}

export async function register(email: string, code: string, password: string): Promise<AuthUser> {
  const data = await request<AuthSession>('/auth/register', { email, code, password });
  saveSession(data, false);
  return data.user;
}

export async function login(email: string, password: string, remember: boolean): Promise<AuthUser> {
  const data = await request<AuthSession>('/auth/login', { email, password, remember });
  saveSession(data, remember);
  return data.user;
}

export async function restoreSession(): Promise<AuthUser | null> {
  const token = readToken();
  if (!token) return null;
  try {
    const user = await request<AuthUser>('/auth/me', undefined, true);
    authState.user = user;
    return user;
  } catch {
    clearSession();
    return null;
  }
}

export async function logout(): Promise<void> {
  try {
    await request('/auth/logout', {}, true);
  } finally {
    clearSession();
  }
}
