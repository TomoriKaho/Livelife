import test from 'node:test';
import assert from 'node:assert/strict';
import { drawerOcclusionHeight, isMapAttributionVisible } from '../src/pages/map/map-drawer-layout.mjs';

const heights = { hidden: 38, middle: 211, expanded: 682 };

test('遮挡高度随抽屉档位变化，拖动时跟手', () => {
  assert.equal(drawerOcclusionHeight('hidden', heights), 38);
  assert.equal(drawerOcclusionHeight('middle', heights), 211);
  assert.equal(drawerOcclusionHeight('expanded', heights), 682);
  assert.equal(drawerOcclusionHeight('middle', heights, { dragging: true, dragHeight: 120 }), 120);
});

test('仅地图仍露出时展示 OSM 署名', () => {
  assert.equal(isMapAttributionVisible('hidden'), true);
  assert.equal(isMapAttributionVisible('middle'), true);
  assert.equal(isMapAttributionVisible('expanded'), false);
});
