import test from 'node:test';
import assert from 'node:assert/strict';
import { drawerHeights, draggedHeight, shouldExpand } from '../src/pages/map/drawer-gesture.mjs';

test('抽屉以实际手机框架计算 1/4、3/4，短屏也不遮住页眉与 Tab', () => {
  assert.deepEqual(drawerHeights(844, 76, 86), { collapsed: 211, expanded: 633 });
  assert.deepEqual(drawerHeights(500, 76, 86), { collapsed: 125, expanded: 338 });
});
test('拖动高度限制在两个停靠位置之间', () => {
  const heights = { collapsed: 180, expanded: 540 };
  assert.equal(draggedHeight(180, -120, heights), 300);
  assert.equal(draggedHeight(180, -900, heights), 540);
  assert.equal(draggedHeight(540, 900, heights), 180);
});
test('横向翻看卡片与轻微触摸不触发展开，明确上滑展开、下滑收起', () => {
  const state = { wasExpanded: false, height: 180, heights: { collapsed: 180, expanded: 540 } };
  assert.equal(shouldExpand({ ...state, deltaX: 100, deltaY: -40 }), false);
  assert.equal(shouldExpand({ ...state, deltaX: 0, deltaY: -4 }), false);
  assert.equal(shouldExpand({ ...state, deltaX: 3, deltaY: -50 }), true);
  assert.equal(shouldExpand({ ...state, wasExpanded: true, deltaX: 3, deltaY: 50 }), false);
});
