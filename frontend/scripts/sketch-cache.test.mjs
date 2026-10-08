import { test } from 'node:test';
import assert from 'node:assert/strict';
import { sketchCacheKey, createSketchStore } from '../src/platform/sketch-cache.ts';

test('disk keys distinguish drawing, DPI, font/theme/renderer compatibility', async () => {
  const a = await sketchCacheKey('<svg width="20"/>', 2);
  assert.equal(a, await sketchCacheKey('<svg width="20"/>', 2));
  assert.match(a, /^[a-f0-9]{64}$/);
  assert.notEqual(a, await sketchCacheKey('<svg width="30"/>', 2));
  assert.notEqual(a, await sketchCacheKey('<svg width="20"/>', 3));
  assert.notEqual(a, await sketchCacheKey('<svg width="20"/>', 2, 'renderer-v2:font-v2:theme-blue'));
});

test('missing IndexedDB degrades to cache miss and harmless writes', async () => {
  const store = createSketchStore();
  assert.equal(await store.get('missing'), undefined);
  await store.put({ key: 'x', blob: new Blob(['png'], { type: 'image/png' }), width: 1, height: 1, touched: 0 });
  await store.remove('x');
  store.close();
  assert.equal(await store.get('x'), undefined);
});
