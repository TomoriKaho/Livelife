import test from 'node:test';
import assert from 'node:assert/strict';
import { drawerHeights, draggedHeight, nextDrawerState, snapDrawerState } from '../src/pages/map/drawer-gesture.mjs';

test('默认 1/4，展开贴合页眉分割线，隐藏后仅保留把手且不遮住 Tab', () => {
  assert.deepEqual(drawerHeights(844, 76, 86), { hidden: 38, middle: 211, expanded: 682 });
  assert.deepEqual(drawerHeights(500, 76, 86), { hidden: 38, middle: 125, expanded: 338 });
  assert.deepEqual(drawerHeights(170, 76, 86), { hidden: 8, middle: 8, expanded: 8 });
});
test('拖动可越过中间档，但不超出隐藏把手与页眉的边界', () => {
  const heights = { hidden: 38, middle: 180, expanded: 540 };
  assert.equal(draggedHeight(180, -120, heights), 300);
  assert.equal(draggedHeight(180, -900, heights), 540);
  assert.equal(draggedHeight(540, 900, heights), 38);
});
test('默认档上滑展开、下滑隐藏，横向翻卡和轻微触摸不换档', () => {
  const state = { fromState: 'middle', height: 180, heights: { hidden: 38, middle: 180, expanded: 540 } };
  assert.equal(snapDrawerState({ ...state, deltaX: 100, deltaY: -40 }), 'middle');
  assert.equal(snapDrawerState({ ...state, deltaX: 0, deltaY: -4 }), 'middle');
  assert.equal(snapDrawerState({ ...state, deltaX: 3, deltaY: -50 }), 'expanded');
  assert.equal(snapDrawerState({ ...state, deltaX: 3, deltaY: 50 }), 'hidden');
  assert.equal(snapDrawerState({ ...state, fromState: 'expanded', height: 490, deltaX: 3, deltaY: 50 }), 'middle');
  assert.equal(snapDrawerState({ ...state, fromState: 'expanded', height: 38, deltaX: 3, deltaY: 502 }), 'hidden');
  assert.equal(snapDrawerState({ ...state, fromState: 'hidden', height: 88, deltaX: 3, deltaY: -50 }), 'middle');
  assert.equal(snapDrawerState({ ...state, fromState: 'hidden', height: 540, deltaX: 3, deltaY: -502 }), 'expanded');
});
test('键盘和点击可恢复隐藏内容，上下换档不会越界', () => {
  assert.equal(nextDrawerState('hidden', 1), 'middle');
  assert.equal(nextDrawerState('middle', 1), 'expanded');
  assert.equal(nextDrawerState('expanded', 1), 'expanded');
  assert.equal(nextDrawerState('expanded', -1), 'middle');
  assert.equal(nextDrawerState('middle', -1), 'hidden');
  assert.equal(nextDrawerState('hidden', -1), 'hidden');
});
