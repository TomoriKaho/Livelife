import test from 'node:test';
import assert from 'node:assert/strict';
import { createFeedbackForm, feedbackRequestId } from '../src/pages/more/feedback-core.ts';

const receipt = { id: '00000000-0000-4000-8000-000000000105', submitted_at: '2026-11-18T08:00:00Z' };
const deferred = () => { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b; }); return { promise, resolve, reject }; };
test('request identities are UUIDs without depending on secure-context randomUUID', () => {
  const ids = Array.from({ length: 50 }, feedbackRequestId);
  assert.equal(new Set(ids).size, 50);
  assert(ids.every(id => /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(id)));
});
function setup(request) {
  let token = 'synthetic-account-a', next = 0;
  const form = createFeedbackForm({ token: () => token, uuid: () => `request-${++next}`, request });
  return { ...form, changeAccount(value) { token = value; form.clear(); } };
}

test('uncertain result keeps draft and retries original UUID, success shows only confirmed receipt', async () => {
  const calls = [];
  const form = setup(async payload => { calls.push(payload); if (calls.length === 1) throw new Error('timeout'); return receipt; });
  form.state.content = '  日历问题  ';
  await form.submit();
  assert.equal(form.state.receipt, null); assert.equal(form.state.content, '  日历问题  ');
  assert.equal(form.state.error, 'timeout');
  await form.submit();
  assert.deepEqual(calls[1], calls[0]); assert.equal(calls[0].content, '日历问题');
  assert.equal(form.state.content, ''); assert.deepEqual(form.state.receipt, receipt);
});
test('new content gets new identity, double click sends once, no eager success', async () => {
  const pending = deferred(), calls = [];
  const form = setup(payload => { calls.push(payload); return pending.promise; });
  form.state.content = '原稿'; const first = form.submit(); await form.submit();
  assert.equal(calls.length, 1); assert.equal(form.state.busy, true); assert.equal(form.state.receipt, null);
  pending.reject(new Error('offline')); await first;
  form.state.content = '新稿'; await form.submit();
  assert.notEqual(calls[0].client_request_id, calls[1].client_request_id);
});
test('switching account clears private drafts and ignores old receipt, error and finally', async () => {
  for (const failed of [false, true]) {
    const old = deferred(), fresh = deferred(); let calls = 0;
    const form = setup(() => ++calls === 1 ? old.promise : fresh.promise);
    form.state.content = '账户 A 的反馈'; const first = form.submit();
    form.changeAccount('synthetic-account-b'); form.state.content = '账户 B 的反馈'; const second = form.submit();
    if (failed) old.reject(new Error('old error')); else old.resolve(receipt);
    await first;
    assert.equal(form.state.content, '账户 B 的反馈'); assert.equal(form.state.busy, true);
    assert.equal(form.state.error, ''); assert.equal(form.state.receipt, null);
    fresh.resolve(receipt); await second;
  }
});
test('unmounted form ignores late results, unauthenticated/empty/oversized submissions never request', async () => {
  let calls = 0; const old = deferred();
  const form = setup(() => { calls++; return old.promise; });
  for (const content of ['', ' \n', '字'.repeat(501), 'a\0b']) { form.state.content = content; await form.submit(); }
  form.changeAccount(null); form.state.content = '未登录'; await form.submit(); assert.equal(calls, 0);
  form.changeAccount('synthetic-account-a'); form.state.content = '😀'.repeat(500); const pending = form.submit();
  assert.equal(calls, 1); form.clear(); old.resolve(receipt); await pending;
  assert.equal(form.state.content, ''); assert.equal(form.state.receipt, null); assert.equal(form.state.busy, false);
});
