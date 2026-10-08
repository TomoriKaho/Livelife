import { reactive } from 'vue';
import { previewState } from './runtime-config.ts';
import type { RuntimeConfig } from './runtime-config.ts';

export interface AndroidConfig extends RuntimeConfig {
  apk_id: string;
  version_code: number;
  version_name: string;
  status_url: string;
  expires: number | null;
}
const origin = import.meta.env?.VITE_TEST_PUBLIC_ORIGIN || 'https://192.144.253.40';
export const androidState = reactive({ config: null as AndroidConfig | null });
export function validateAndroidConfig(value: unknown, publicOrigin = origin): AndroidConfig {
  const c = value as AndroidConfig;
  if (!c || c.schema_version !== 1 || !/^[a-f0-9]{32}$/.test(c.apk_id)
    || c.build_id !== `apk-${c.apk_id}` || !/^[a-f0-9]{40}$/.test(c.frontend_sha)
    || !/^[a-f0-9]{40}$/.test(c.backend_sha) || !['staging', 'own', 'fixed'].includes(c.backend_mode)
    || !Number.isInteger(c.version_code) || c.version_code < 1 || c.version_code > 2100000000
    || c.version_name !== `0.1.0-test.${c.version_code}`
    || !(c.expires === null || (Number.isFinite(c.expires) && c.expires > 0))) {
    throw new Error('安装包配置无效。');
  }
  const api = new URL(c.api_base_url);
  const expected = c.backend_mode === 'staging' ? '/api/staging/' : `/api/versions/be-${c.backend_sha}/`;
  const status = new URL(c.status_url);
  if (api.origin !== publicOrigin || api.pathname !== expected || api.search || api.hash || api.username || api.password
    || status.href !== `${publicOrigin}/downloads/android/build-${c.apk_id}/status.json`) {
    throw new Error('安装包后端地址与版本不匹配。');
  }
  return c;
}
async function readJson(url: string) {
  const response = await fetch(url, { cache: 'no-store', signal: AbortSignal.timeout(5000) });
  if (response.status !== 200) throw new Error(`读取安装包状态失败（HTTP ${response.status}）。`);
  return response.json();
}
export async function checkAndroidStatus() {
  const c = androidState.config;
  if (!c) return;
  // Fail closed while revalidating. Bundled sample pages remain available offline.
  previewState.config = null;
  previewState.error = '';
  try {
    const live = await readJson(c.status_url);
    if (live.apk_id !== c.apk_id || live.version_code !== c.version_code || live.frontend_sha !== c.frontend_sha
      || live.backend_mode !== c.backend_mode || live.backend_sha !== c.backend_sha || live.status !== 'ready'
      || (live.expires !== null && (!Number.isFinite(live.expires) || Date.now() >= live.expires * 1000))) {
      throw new Error('测试包已过期或被释放，请下载新的测试包。');
    }
    previewState.config = c;
  } catch (error) {
    previewState.error = error instanceof Error ? error.message : '无法确认安装包状态，请联网重试。';
    throw error;
  }
}
export async function loadAndroidConfig() {
  previewState.enabled = true;
  previewState.loading = true;
  previewState.config = null;
  try {
    androidState.config = validateAndroidConfig(await readJson('./native-config.json'));
    await checkAndroidStatus();
  } catch (error) {
    previewState.error = error instanceof Error ? error.message : '无法读取安装包配置。';
  } finally { previewState.loading = false; }
}
