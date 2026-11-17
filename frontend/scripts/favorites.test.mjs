import test from 'node:test';
import assert from 'node:assert/strict';
import { createFavorites } from '../src/state/favorites-core.ts';

const deferred = () => { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b; }); return { promise, resolve, reject }; };
const item = id => ({ id, status: 'upcoming' });
const page = (ids = [], next = null) => ({ items: ids.map(item), counts: { upcoming: ids.length, ongoing: 0, ended: 0, unknown: 0 }, total: ids.length, as_of: '2026-11-16T08:00:00Z', next_offset: next });
function setup(overrides = {}) {
  let token = 'account-a';
  const store = createFavorites({ token: () => token, membership: async () => [], page: async () => page(), write: async () => {}, ...overrides });
  return { ...store, changeAccount: value => { token = value; store.clear(); } };
}

test('only confirmed writes change shared state, duplicate clicks do not issue another request', async () => {
  const write = deferred(); let calls = 0;
  const store = setup({ write: () => { calls++; return write.promise; } });
  store.state.saved.a = false;
  const first = store.set('a', true);
  assert.equal(store.state.saved.a, false);
  assert.equal(await store.set('a', true), false);
  assert.equal(calls, 1);
  write.resolve(); assert.equal(await first, true);
  assert.equal(store.state.saved.a, true);
  assert.equal(store.state.pending.a, false);
});
test('failed writes retain confirmed state and show a recoverable error', async () => {
  const store = setup({ write: async () => { throw new Error('offline'); } });
  store.state.saved.a = true;
  assert.equal(await store.set('a', false), false);
  assert.equal(store.state.saved.a, true);
  assert.equal(store.state.errors.a, 'offline');
});
test('late membership and list responses cannot resurrect a removed favorite', async () => {
  const membership = deferred(), list = deferred();
  let lists = 0;
  const store = setup({ membership: () => membership.promise, page: () => ++lists === 1 ? list.promise : Promise.resolve(page()) });
  const check = store.check(['a']); const loading = store.load();
  assert.equal(await store.set('a', false), true);
  membership.resolve(['a']); list.resolve(page(['a']));
  await Promise.all([check, loading]);
  assert.equal(store.state.saved.a, false);
  assert.deepEqual(store.state.items, []);
});
test('account switch rejects late writes, reads, errors and finally handlers', async () => {
  const write = deferred(), membership = deferred(), list = deferred();
  const store = setup({ write: () => write.promise, membership: () => membership.promise, page: () => list.promise });
  const jobs = [store.set('a', true), store.check(['a']), store.load()];
  store.changeAccount('account-b');
  store.state.saved.b = true;
  write.reject(new Error('old account failure')); membership.resolve(['a']); list.resolve(page(['a']));
  await Promise.all(jobs);
  assert.deepEqual({ ...store.state.saved }, { b: true });
  assert.deepEqual({ ...store.state.pending }, {});
  assert.deepEqual({ ...store.state.errors }, {});
  assert.deepEqual(store.state.items, []);
});
test('pagination keeps its classification instant and de-duplicates boundary entries', async () => {
  const calls = [];
  const store = setup({ page: async (...args) => { calls.push(args); return calls.length === 1 ? page(['a'], 20) : page(['a', 'b']); } });
  await store.load(); await store.load(true);
  assert.deepEqual(store.state.items.map(i => i.id), ['a', 'b']);
  assert.deepEqual(calls[1], ['upcoming', 20, '2026-11-16T08:00:00Z']);
});
test('a late response from a previously selected category cannot replace the new list', async () => {
  const old = deferred(); let calls = 0;
  const store = setup({ page: async () => ++calls === 1 ? old.promise : page(['b']) });
  const first = store.load(); store.state.category = 'unknown'; await store.load();
  old.resolve(page(['a'])); await first;
  assert.deepEqual(store.state.items.map(i => i.id), ['b']);
});
test('membership batches have at most 100 ids and clear stale results after logout', async () => {
  const batches = [];
  const store = setup({ membership: async ids => { batches.push(ids); return ids.slice(0, 1); } });
  await store.check(Array.from({ length: 205 }, (_, i) => String(i)));
  assert.deepEqual(batches.map(batch => batch.length), [100, 100, 5]);
  store.changeAccount(null);
  await store.load(); assert.equal(await store.set('a', true), false);
  assert.deepEqual(store.state.items, []);
});
