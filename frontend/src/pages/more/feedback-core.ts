import type { FeedbackReceipt, FeedbackSubmission } from '../../api/feedback';

export interface FeedbackState {
  content: string; busy: boolean; error: string; receipt: FeedbackReceipt | null;
}

/** getRandomValues also works on local HTTP device previews without randomUUID. */
export function feedbackRequestId() {
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6]! & 0x0f) | 0x40;
  bytes[8] = (bytes[8]! & 0x3f) | 0x80;
  const hex = Array.from(bytes, value => value.toString(16).padStart(2, '0')).join('');
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

/** Keep uncertain submissions in memory, with the same identity until edited. */
export function createFeedbackForm(deps: {
  token: () => string | null;
  request: (payload: FeedbackSubmission) => Promise<FeedbackReceipt>;
  uuid: () => string;
  reactive?: (state: FeedbackState) => FeedbackState;
}) {
  const blank = (): FeedbackState => ({ content: '', busy: false, error: '', receipt: null });
  const state = deps.reactive ? deps.reactive(blank()) : blank();
  let epoch = 0, attempt: FeedbackSubmission | null = null;
  function clear() { epoch++; attempt = null; Object.assign(state, blank()); }
  async function submit() {
    if (state.busy) return;
    const content = state.content.trim(), token = deps.token();
    state.error = '';
    if (!token) { state.error = '请先登录后提交反馈。'; return; }
    if (!content || Array.from(content).length > 500 || content.includes('\0')) {
      state.error = '请填写 1–500 字反馈。'; return;
    }
    const current = epoch;
    const active = () => epoch === current && token === deps.token();
    state.busy = true; state.receipt = null;
    try {
      if (!attempt || attempt.content !== content) attempt = { client_request_id: deps.uuid(), content };
      const payload = { ...attempt };
      const receipt = await deps.request(payload);
      if (!active()) return;
      state.receipt = receipt;
      if (state.content.trim() === content) state.content = '';
      attempt = null;
    } catch (error) {
      if (active()) state.error = error instanceof Error ? error.message : '提交未完成，请重试。';
    } finally {
      if (active()) state.busy = false;
    }
  }
  return { state, submit, clear };
}
