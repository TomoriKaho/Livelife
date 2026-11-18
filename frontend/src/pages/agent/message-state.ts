export type AgentMessageStatus = 'pending' | 'completed' | 'failed' | 'cancelled';

export interface MessageStateInput {
  role: string;
  status: string;
  text?: string;
  errorCode?: string | null;
}

const FAILURE_NOTICES: Record<string, string> = {
  token_quota_exceeded: '你的账号今日的使用额度已用完。',
  request_in_progress: '该请求仍在生成中，请稍候刷新对话状态或再试。',
  user_request_in_progress: '你的上一条提问仍在生成中，请稍候再试。',
  user_rate_limited: '提问过于频繁，请稍后再试。',
  ip_rate_limited: '当前网络请求过于频繁，请稍后再试。',
  request_conflict: '请求标识冲突，请刷新对话后再试。',
  model_length_limit: '回答达到单次输出长度上限，未完整生成。',
  model_content_filtered: '回答触发内容安全限制，未完整生成。',
  model_timeout: '回答生成超时，请点击重试。',
  model_incomplete_stream: '回答传输异常中断，请点击重试。',
  incomplete_stream: '连接中断，请点击重试恢复回答。',
};

const PARTIAL_STATUS_NOTES: Record<string, string> = {
  model_length_limit: '达到单次输出长度上限，回答未完整生成。',
  model_content_filtered: '回答因内容安全策略中止，未完整生成。',
  model_timeout: '生成超时，回答未完整生成，可点击重试。',
  model_incomplete_stream: '上游连接中断，回答未完整生成，可点击重试。',
  incomplete_stream: '连接中断，回答未完整生成，可点击重试。',
  request_expired: '生成中断，回答未完整生成，可点击重试。',
};

const EMPTY_STATUS_NOTES: Record<string, string> = {
  model_length_limit: '达到单次输出长度上限，未能生成可见回答。',
  model_content_filtered: '回答因内容安全策略中止，未能生成内容。',
  model_timeout: '生成超时，尚未产生回答，请点击重试。',
  model_incomplete_stream: '上游连接中断，未收到完整回答，请点击重试。',
  incomplete_stream: '连接中断，未收到完整回答，请点击重试。',
  request_expired: '生成未完成，请点击重试。',
};

export function canRetryMessage(message: Pick<MessageStateInput, 'role' | 'status'>): boolean {
  return (message.role === 'agent' || message.role === 'assistant')
    && (message.status === 'failed' || message.status === 'cancelled');
}

export function isTransientBusyError(code: string): boolean {
  return code === 'request_in_progress' || code === 'user_request_in_progress';
}

export function messageStatusNote(message: MessageStateInput): string {
  if (message.role !== 'agent' && message.role !== 'assistant') return '';
  const hasText = Boolean(message.text?.trim());
  if (message.status === 'cancelled') {
    return hasText ? '回答已中断，内容未完整生成，可点击重试。' : '回答已中断，可点击重试。';
  }
  if (message.status !== 'failed') return '';
  const code = message.errorCode || '';
  if (hasText) {
    return PARTIAL_STATUS_NOTES[code] || '回答未完整生成，可点击重试。';
  }
  return EMPTY_STATUS_NOTES[code] || '回答生成失败，请点击重试。';
}

export function failureNoticeText(code: string): string {
  return FAILURE_NOTICES[code] || '回答失败，请点击重试。';
}
