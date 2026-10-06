/**
 * 首阶段唯一的真实后端接口：GET /test/hello
 *
 * 接口契约见 docs/architecture.md#首阶段接口契约
 */

import type { HelloResponse } from '../types';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

/** 调用后端 hello 接口，返回原始响应或错误信息 */
export async function fetchHello(): Promise<
  | { ok: true; data: HelloResponse }
  | { ok: false; error: string }
> {
  try {
    const resp = await fetch(`${BASE_URL}/test/hello`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
    });
    if (!resp.ok) {
      return { ok: false, error: `HTTP ${resp.status}` };
    }
    const json: unknown = await resp.json();
    if (typeof json === 'object' && json !== null && 'message' in json) {
      return { ok: true, data: json as HelloResponse };
    }
    return { ok: false, error: '响应格式不符' };
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : '网络请求失败' };
  }
}