import test from 'node:test';
import assert from 'node:assert/strict';
import { isMapAttributionVisible } from '../src/pages/map/map-drawer-layout.mjs';

const heights = { hidden: 38, middle: 211, expanded: 682 };

test('隐藏档与默认档展示署名，全展开不展示', () => {
  assert.equal(isMapAttributionVisible(heights.hidden, heights.expanded), true);
  assert.equal(isMapAttributionVisible(heights.middle, heights.expanded), true);
  assert.equal(isMapAttributionVisible(heights.expanded, heights.expanded), false);
});

test('从展开档向下拖动、尚未松手换档时，地图露出就展示署名', () => {
  for (const renderedHeight of [620, 450, 211, 38]) {
    assert.equal(isMapAttributionVisible(renderedHeight, heights.expanded), true);
  }
});

test('吸附动画以实际高度判断，最终完全遮挡后隐藏', () => {
  for (const renderedHeight of [211, 450, 620]) {
    assert.equal(isMapAttributionVisible(renderedHeight, heights.expanded), true);
  }
  assert.equal(isMapAttributionVisible(681.75, heights.expanded), false);
  assert.equal(isMapAttributionVisible(682, heights.expanded), false);
});

test('无可用地图区域或尺寸无效时不展示', () => {
  for (const [occlusion, expanded] of [[0, 0], [100, 90], [NaN, 682], [211, NaN], [-1, 682]]) {
    assert.equal(isMapAttributionVisible(occlusion, expanded), false);
  }
});
