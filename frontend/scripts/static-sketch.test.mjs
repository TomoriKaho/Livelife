import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { decorationState } from '../src/plugins/static-sketch.ts';

const element = (classes, dataset = {}) => ({ dataset, classList: { contains: value => classes.includes(value) } });
test('selection changes switch pigment and white paper without retaining the previous state', () => {
  assert.deepEqual(decorationState(element(['sketch-white', 'sketch-cast'], { pencil: 'blue', cast: 'yellow' })),
    { color: 'blue', cast: 'yellow', white: false, fillOnly: false, faint: false });
  assert.deepEqual(decorationState(element(['sketch-white', 'sketch-cast'], { cast: 'yellow' })),
    { color: '', cast: 'yellow', white: true, fillOnly: false, faint: false });
  assert.equal(decorationState(element(['sketch-white'], { pencil: 'unknown' })).white, true);
  assert.equal(decorationState(element(['sketch-fill-only'])).fillOnly, true);
  assert.equal(decorationState(element(['nav-item'], { pencil: 'blue' })).cast, 'yellow');
});
test('committed default assets have bounded decoded cost and valid 3x PNG dimensions', async () => {
  const root = new URL('../src/assets/sketch/default/', import.meta.url);
  const manifest = JSON.parse(await readFile(new URL('manifest.json', root), 'utf8'));
  assert.equal(manifest.theme, 'default'); assert.equal(manifest.assets.length, 17);
  let pixels = 0, bytes = 0;
  for (const asset of manifest.assets) {
    const png = await readFile(new URL(`${asset.name}.png`, root));
    assert.equal(png.subarray(0, 8).toString('hex'), '89504e470d0a1a0a');
    assert.equal(png.readUInt32BE(16), asset.width);
    assert.equal(png.readUInt32BE(20), asset.height);
    assert.equal(png.length, asset.bytes);
    pixels += asset.width * asset.height; bytes += png.length;
  }
  assert.ok(bytes < 256 * 1024, 'default decorations must stay under 256 KiB');
  assert.ok(pixels * 4 < 3 * 1024 * 1024, 'decoded PNGs must stay under 3 MiB');
});
