import { strict as assert } from 'node:assert';
import { test } from 'node:test';
import { composerPlacement, compactInputHeight } from '../src/pages/agent/composer-layout.mjs';

const mobile = { shellTop: 0, shellBottom: 800, navigationHeight: 86, viewportTop: 0, viewportHeight: 800, restingHeight: 800, focused: true };
test('closed keyboard keeps the composer above navigation', () => {
  assert.deepEqual(composerPlacement(mobile), { keyboardOpen: false, bottom: 86, top: 0 });
});
test('overlay keyboard places the bottom eight pixels above its edge', () => {
  assert.deepEqual(composerPlacement({ ...mobile, viewportHeight: 480 }), { keyboardOpen: true, bottom: 328, top: 0 });
});
test('resized layout viewport does not leave a navigation-height gap above keyboard', () => {
  assert.equal(composerPlacement({ ...mobile, shellBottom: 480, viewportHeight: 480 }).bottom, 8);
});
test('panned visual viewport offsets both edges; desktop phone frame is supported', () => {
  assert.deepEqual(composerPlacement({ ...mobile, shellTop: 24, shellBottom: 696, viewportTop: 90, viewportHeight: 400 }), { keyboardOpen: true, bottom: 214, top: 66 });
});
test('pinch zoom and unfocused window resize are not treated as keyboard opening', () => {
  assert.equal(composerPlacement({ ...mobile, viewportHeight: 400, scale: 2 }).keyboardOpen, false);
  assert.equal(composerPlacement({ ...mobile, viewportHeight: 400, focused: false }).keyboardOpen, false);
});
test('keyboard dismissal follows viewport animation until it closes', () => {
  assert.equal(composerPlacement({ ...mobile, viewportHeight: 600, focused: false, keyboardWasOpen: true }).bottom, 208);
  assert.equal(composerPlacement({ ...mobile, focused: false, keyboardWasOpen: true }).bottom, 86);
});
test('compact editor caps text at three and a half lines without counting padding', () => {
  assert.equal(compactInputHeight(44, 24, 20), 44);
  assert.equal(compactInputHeight(92, 24, 20), 92);
  assert.equal(compactInputHeight(116, 24, 20), 104);
  assert.equal(compactInputHeight(500, 24, 20), 104);
});
