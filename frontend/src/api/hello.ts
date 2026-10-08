/**
 * 首阶段唯一的真实后端接口：GET /test/hello
 * 接口契约见 docs/architecture.md#首阶段接口契约。
 */
import { checkAndroidStatus } from '../platform/android-config';
import type { HelloResponse } from '../types';
import { getApiBaseUrl } from '../platform/web';
import { previewState } from '../platform/runtime-config';

/** 仅将 HTTP 200 和约定的 hello world 响应判定为成功。 */
export async function fetchHello(): Promise<
  | { ok: true; data: HelloResponse }
  | { ok: false; error: string }
> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 10_000);
  try {
    await checkAndroidStatus();
    const baseUrl = getApiBaseUrl().replace(/\/+$/, '');
    const resp = await fetch(`${baseUrl}/test/hello`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
      signal: controller.signal,
    });
    const responseSha = resp.headers.get('X-Livelife-Backend-SHA');
    if (responseSha && /^[0-9a-f]{40}$/.test(responseSha)) previewState.observedBackendSha = responseSha;
    if (previewState.enabled && previewState.config && (responseSha === null
      || !/^[0-9a-f]{40}$/.test(responseSha)
      || (previewState.config.backend_mode !== 'staging' && responseSha !== previewState.config.backend_sha))) {
      return { ok: false, error: '响应后端版本与测试配置不符，请刷新配置并检查部署状态。' };
    }
    if (resp.status !== 200) {
      return { ok: false, error: `后端返回 HTTP ${resp.status}（期望 HTTP 200）` };
    }
    const json: unknown = await resp.json();
    if (typeof json === 'object' && json !== null && 'message' in json && json.message === 'hello world') {
      return { ok: true, data: { message: json.message } };
    }
    return { ok: false, error: '响应格式不符：应返回 message 为 hello world 的 JSON 对象。' };
  } catch (error) {
    if (controller.signal.aborted) return { ok: false, error: '连接超时，请稍后重试。' };
    if (error instanceof SyntaxError) return { ok: false, error: '后端响应不是有效的 JSON。' };
    return { ok: false, error: '无法连接后端，请检查后端地址和服务状态。' };
  } finally {
    clearTimeout(timeout);
  }
}
