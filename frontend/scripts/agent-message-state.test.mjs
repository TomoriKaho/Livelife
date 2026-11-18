import test from 'node:test';
import assert from 'node:assert/strict';
import {
  canRetryMessage,
  failureNoticeText,
  isTransientBusyError,
  messageStatusNote,
} from '../src/pages/agent/message-state.ts';

test('only failed or cancelled assistant messages expose retry', () => {
  assert.equal(canRetryMessage({ role: 'agent', status: 'failed' }), true);
  assert.equal(canRetryMessage({ role: 'assistant', status: 'cancelled' }), true);
  assert.equal(canRetryMessage({ role: 'agent', status: 'completed' }), false);
  assert.equal(canRetryMessage({ role: 'agent', status: 'pending' }), false);
  assert.equal(canRetryMessage({ role: 'user', status: 'failed' }), false);
});

test('marks partial EOF, length truncation and cancellation clearly without mislabeling completed replies', () => {
  assert.equal(messageStatusNote({ role: 'agent', status: 'completed', text: '完整回答' }), '');
  assert.equal(messageStatusNote({ role: 'agent', status: 'pending', text: '流式片段' }), '');
  assert.match(
    messageStatusNote({ role: 'agent', status: 'failed', text: '半截文本', errorCode: 'model_incomplete_stream' }),
    /未完整生成/,
  );
  assert.match(
    messageStatusNote({ role: 'agent', status: 'failed', text: '截断文本', errorCode: 'model_length_limit' }),
    /长度上限.*未完整生成/,
  );
  assert.match(
    messageStatusNote({ role: 'agent', status: 'cancelled', text: '中途停下' }),
    /已中断.*未完整生成/,
  );
  assert.match(
    messageStatusNote({ role: 'agent', status: 'failed', text: '', errorCode: 'model_timeout' }),
    /超时/,
  );
});

test('identifies in-progress conflicts and maps failure notices', () => {
  assert.equal(isTransientBusyError('request_in_progress'), true);
  assert.equal(isTransientBusyError('user_request_in_progress'), true);
  assert.equal(isTransientBusyError('model_timeout'), false);
  assert.match(failureNoticeText('token_quota_exceeded'), /额度已用完/);
  assert.match(failureNoticeText('request_in_progress'), /仍在生成中/);
  assert.match(failureNoticeText('model_length_limit'), /长度上限/);
});
