import { reactive } from 'vue';

export interface RuntimeConfig {
  schema_version: 1;
  environment: string;
  frontend_sha: string;
  build_id: string;
  api_base_url: string;
  backend_mode: 'staging' | 'own' | 'fixed';
  backend_sha: string;
}

const commit = /^[0-9a-f]{40}$/;
export function validateRuntimeConfig(value: unknown, origin: string): RuntimeConfig {
  if (!value || typeof value !== 'object') throw new Error('测试配置格式错误。');
  const config = value as RuntimeConfig;
  if (config.schema_version !== 1 || !/^(main|branch-[0-9a-f]{32})$/.test(config.environment)
    || !commit.test(config.frontend_sha) || !commit.test(config.backend_sha)
    || !/^fe-[0-9a-f]{40}-[1-9][0-9]*-[1-9][0-9]*$/.test(config.build_id)
    || !config.build_id.startsWith(`fe-${config.frontend_sha}-`)
    || !['staging', 'own', 'fixed'].includes(config.backend_mode)) {
    throw new Error('测试配置版本或字段无效。');
  }
  const api = new URL(config.api_base_url, origin);
  if (api.origin !== origin || api.username || api.password || api.search || api.hash
    || !/^\/api\/(staging|versions\/be-[0-9a-f]{40})\/$/.test(api.pathname)
    || (config.backend_mode !== 'staging' && api.pathname !== `/api/versions/be-${config.backend_sha}/`)
    || (config.backend_mode === 'staging' && api.pathname !== '/api/staging/')) {
    throw new Error('测试后端地址与版本不匹配。');
  }
  return { ...config, api_base_url: api.href };
}

export const previewState = reactive({
  enabled: false,
  loading: false,
  config: null as RuntimeConfig | null,
  error: '',
  observedBackendSha: '',
});

export async function loadPreviewConfig(
  enabled = import.meta.env?.VITE_WEB_PREVIEW === 'true',
  pageUrl?: string,
  expectedBuildId = import.meta.env?.VITE_WEB_BUILD_ID,
) {
  previewState.enabled = enabled;
  if (!enabled) return;
  previewState.loading = true;
  previewState.error = '';
  previewState.config = null;
  previewState.observedBackendSha = '';
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 5_000);
  try {
    const page = new URL(pageUrl ?? window.location.href);
    const response = await fetch(new URL('./runtime-config.json', page), {
      cache: 'no-store', credentials: 'same-origin', signal: controller.signal,
    });
    if (response.status !== 200) throw new Error(`读取测试配置失败（HTTP ${response.status}）。`);
    const config = validateRuntimeConfig(await response.json(), page.origin);
    if (expectedBuildId && config.build_id !== expectedBuildId) throw new Error('页面版本已更新，请刷新页面后重试。');
    previewState.config = config;
  } catch (error) {
    previewState.error = error instanceof Error ? error.message : '无法读取测试配置，请重试。';
  } finally {
    clearTimeout(timeout);
    previewState.loading = false;
  }
}
