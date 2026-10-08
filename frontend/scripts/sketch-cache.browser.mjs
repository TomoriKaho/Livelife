// Run from a Vite page: await (await import('/scripts/sketch-cache.browser.mjs')).verifySketchCache()
import { createSketchStore } from '../src/platform/sketch-cache.ts';
import { createSketchBitmapQueue } from '../src/plugins/sketch-bitmap.ts';

export async function verifySketchCache() {
  const results = [], stores = [], queues = [];
  const name = `livelife-cache-test-${crypto.randomUUID()}`;
  const assert = (ok, message) => { if (!ok) throw new Error(message); results.push(message); };
  const makeStore = budget => { const s = createSketchStore(name, budget); stores.push(s); return s; };
  const canvas = document.createElement('canvas'); canvas.width = canvas.height = 4;
  canvas.getContext('2d').fillRect(0, 0, 4, 4);
  const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/png'));
  const record = key => ({ key, blob, width: 4, height: 4, touched: Date.now() });
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.innerHTML = '<rect width="20" height="20" fill="blue"/>';
  const draw = async queue => {
    let release, count = 0;
    queue.render(svg, 20, 20, (_image, free) => { release = free; count++; }, "test-frame");
    await queue.whenIdle(); release?.();
    assert(count === 1, 'drawing published exactly once');
  };
  try {
    let store = makeStore(blob.size * 2);
    await store.put(record('a')); store.close(); store = makeStore(blob.size * 2);
    assert((await store.get('a'))?.blob.size === blob.size, 'PNG survives closed connection/reopen');
    await store.put(record('b')); await store.get('a'); await store.put(record('c'));
    assert(await store.get('b') === undefined && !!await store.get('a') && !!await store.get('c'), 'budget evicts least recently used record');
    await store.remove('a'); assert(await store.get('a') === undefined, 'explicit cache removal');
    const db = await new Promise(resolve => { const r = indexedDB.open(name); r.onsuccess = () => resolve(r.result); });
    const tx = db.transaction(['images', 'metadata'], 'readwrite');
    tx.objectStore('images').put(record('interrupted')); tx.abort();
    await new Promise(resolve => { tx.onabort = resolve; }); db.close();
    assert(await store.get('interrupted') === undefined, 'aborted write leaves no readable candidate');
    store.close();
    let q = createSketchBitmapQueue(makeStore()); queues.push(q);
    assert(!await q.restore(), 'missing prepared marker falls back to warmup');
    await draw(q);
    assert(q.stats.generated === 1 && q.stats.diskHits === 0, 'cold miss generates PNG');
    const secondSvg = svg.cloneNode(true); secondSvg.firstElementChild.setAttribute('fill', 'red');
    q.render(secondSvg, 20, 20, (_image, release) => release(), 'second-frame');
    await q.whenIdle(); await q.markPrepared(); q.dispose();
    q = createSketchBitmapQueue(makeStore()); queues.push(q);
    assert(await q.restore() && q.stats.restored === 2, 'entire two-image set decoded before alias publication');
    let aliasHit = false;
    q.reuse('test-frame', (image, release) => { aliasHit = image.classList.contains('sketch-bitmap'); release(); });
    await q.whenIdle();
    assert(aliasHit && q.stats.generated === 0, 'restored alias bypasses SVG construction');
    let secondHit = false; q.reuse('second-frame', (_image, release) => { secondHit = true; release(); });
    assert(secondHit, 'other-page alias is immediately decoded');
    assert(q.stats.generated === 0 && q.stats.diskHits === 2, 'new queue uses whole disk set without encoding'); q.dispose();
    const raw = await new Promise(resolve => { const r = indexedDB.open(name); r.onsuccess = () => resolve(r.result); });
    const corrupt = raw.transaction('images', 'readwrite');
    const cursor = corrupt.objectStore('images').openCursor();
    cursor.onsuccess = () => { const c = cursor.result; if (c) { if (c.value.identity === 'test-frame') c.update({ ...c.value, blob: new Blob(['broken'], { type: 'image/png' }) }); c.continue(); } };
    await new Promise(resolve => { corrupt.oncomplete = resolve; }); raw.close();
    q = createSketchBitmapQueue(makeStore()); queues.push(q);
    assert(!await q.restore(), 'corrupt full set falls back before publishing any alias');
    assert(q.reuse('test-frame', () => {}) === undefined && q.reuse('second-frame', () => {}) === undefined, 'failed full restore leaves no partial visible cache');
    await draw(q);
    assert(q.stats.generated === 1 && q.stats.diskHits === 0, 'corrupt PNG regenerates successfully'); q.dispose();
    q = createSketchBitmapQueue(makeStore()); queues.push(q); await draw(q);
    assert(q.stats.diskHits === 1, 'regenerated record persists'); q.dispose();
    const unavailable = { get: async () => { throw new Error('storage denied'); }, put: async () => { throw new Error('quota'); }, remove: async () => {}, close() {} };
    q = createSketchBitmapQueue(unavailable); queues.push(q); await draw(q);
    assert(q.stats.generated === 1, 'storage denial/quota failure preserves drawing'); q.dispose();
    let complete;
    const late = { ...unavailable, get: () => new Promise(resolve => { complete = resolve; }) };
    q = createSketchBitmapQueue(late); queues.push(q);
    let published = false;
    q.render(svg, 20, 20, () => { published = true; });
    while (!complete) await new Promise(resolve => setTimeout(resolve, 0));
    q.dispose(); complete(undefined); await q.whenIdle();
    assert(!published, 'disposed queue never publishes late storage results');
    return results;
  } finally {
    queues.forEach(q => q.dispose()); stores.forEach(s => s.close());
    await new Promise(resolve => { const r = indexedDB.deleteDatabase(name); r.onsuccess = r.onerror = resolve; });
  }
}
