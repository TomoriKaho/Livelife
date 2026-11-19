import { authState, clearSession, readAuthToken } from './auth';
import { checkAndroidStatus } from '../platform/android-config';
import { previewState } from '../platform/runtime-config';
import { getApiBaseUrl } from '../platform/web';

export interface FeedbackReceipt { id: string; submitted_at: string }
export interface FeedbackSubmission { client_request_id: string; content: string }

export async function submitFeedback(payload: FeedbackSubmission): Promise<FeedbackReceipt> {
  const token = readAuthToken(), revision = authState.revision;
  if (!token) throw new Error('请先登录后提交反馈。');
  const assertIdentity = () => {
    if (token !== readAuthToken() || revision !== authState.revision) throw new Error('登录状态已变更，请重试。');
  };
  await checkAndroidStatus(); assertIdentity();
  if (previewState.enabled && !previewState.config) throw new Error(previewState.error || '测试配置不可用。');
  let response: Response, data: unknown;
  try {
    response = await fetch(`${getApiBaseUrl().replace(/\/+$/, '')}/feedback`, {
      method: 'POST', headers: { Accept: 'application/json', 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify(payload), signal: AbortSignal.timeout(15_000),
    });
    data = await response.json();
  } catch {
    throw new Error('未能确认提交结果，请检查网络后重试。正文已保留，重试会避免重复提交。');
  }
  assertIdentity();
  const expected = previewState.enabled ? previewState.config : null;
  const sha = response.headers.get('X-Livelife-Backend-SHA');
  if (previewState.enabled && (!expected || !sha || !/^[0-9a-f]{40}$/.test(sha)
    || (expected.backend_mode !== 'staging' && expected.backend_sha !== sha))) throw new Error('响应后端版本与测试配置不符，请刷新配置后重试。');
  if (response.status === 401) { clearSession(); throw new Error('登录已过期，请重新登录。'); }
  if (response.status === 429) {
    const seconds = Number(response.headers.get('Retry-After'));
    throw new Error(`提交过于频繁，${Number.isFinite(seconds) && seconds > 0 ? `请在 ${Math.ceil(seconds)} 秒后` : '请稍后'}重试。正文已保留。`);
  }
  if (response.status === 409) throw new Error('提交编号与正文不一致，请修改正文后重新提交。');
  if (response.status === 422) throw new Error('请填写 1–500 字反馈，且不要包含特殊控制字符。');
  if (!response.ok) throw new Error(`暂时无法确认提交结果（HTTP ${response.status}），请稍后重试。正文已保留。`);
  const receipt = data as FeedbackReceipt;
  if (![200, 201].includes(response.status) || !receipt || typeof receipt.id !== 'string'
    || !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(receipt.id)
    || typeof receipt.submitted_at !== 'string' || !Number.isFinite(Date.parse(receipt.submitted_at))) {
    throw new Error('回执格式不正确，尚未确认提交结果；请使用保留的正文重试。');
  }
  return receipt;
}
