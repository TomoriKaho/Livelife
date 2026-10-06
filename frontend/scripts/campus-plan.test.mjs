import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { center, constrainToBoundary } from '../src/pages/map/geometry.mjs';
import { demoLocation } from '../src/pages/map/demo.js';
import { initialPlanScale, planAnchor, worldToPlan, planToWorld, zoomPlan, panPlan, pinchPlan, pickPlanBuilding, planScaleBar, planLimits } from '../src/pages/map/plan-view.mjs';
const campus = JSON.parse(readFileSync(new URL('../src/assets/maps/campus.json', import.meta.url), 'utf8'));
const boundary = [[-1000, -1000], [1000, -1000], [1000, 1000], [-1000, 1000]];
const close = (a, b) => a.forEach((value, i) => assert.ok(Math.abs(value - b[i]) < 1e-7));

test('手机尺寸和抽屉上方定位点投影一致，北向在上，屏幕/米制坐标可互相转换', () => {
  for (const width of [320, 390, 430]) {
    const anchor = planAnchor(width, 680, 180), view = { center: [...demoLocation], scale: initialPlanScale(width) };
    close(worldToPlan(demoLocation, view, anchor), anchor);
    assert.ok(worldToPlan([175, 35], view, anchor)[1] < anchor[1]);
    const point = [36, 250]; close(planToWorld(worldToPlan(point, view, anchor), view, anchor), point);
  }
});
test('鼠标/手指锚点缩放保持同一地理点，并限制最大与最小倍率', () => {
  const view = { center: [0, 0], scale: .5 }, anchor = [195, 280], point = [120, 200];
  const world = planToWorld(point, view, anchor);
  close(planToWorld(point, zoomPlan(view, 1.2, point, anchor, boundary), anchor), world);
  assert.equal(zoomPlan(view, 100, anchor, anchor, boundary).scale, planLimits.maxScale);
  assert.equal(zoomPlan(view, 0, anchor, anchor, boundary).scale, planLimits.minScale);
});
test('双指中点移动与间距扩大同步平移、放大，指下地图不跳动', () => {
  const view = { center: [0, 0], scale: .5 }, anchor = [195, 280];
  const before = [[100, 200], [200, 200]], after = [[75, 230], [275, 230]];
  const next = pinchPlan(view, before, after, anchor, boundary);
  assert.equal(next.scale, 1);
  close(planToWorld([175, 230], next, anchor), planToWorld([150, 200], view, anchor));
  const coincident = pinchPlan(view, [[100, 200], [100, 200]], before, anchor, boundary);
  assert.ok(Number.isFinite(coincident.scale) && coincident.center.every(Number.isFinite));
});
test('拖动按实际凹形校界约束观察中心，不裁去校外建筑背景', () => {
  const view = { center: [...demoLocation], scale: .5 };
  const next = panPlan(view, [-5000, -5000], campus.boundary);
  close(constrainToBoundary(next.center, campus.boundary), next.center);
  assert.ok(campus.context.buildings.length > 0);
});
test('真实建筑可点选，图书馆庭院不误选，校外背景不参与选择', () => {
  const library = campus.buildings.find(item => item.id === 'r3249649');
  assert.equal(pickPlanBuilding([-65, 64], [library]), library.id);
  for (const hole of library.holes) assert.equal(pickPlanBuilding(center(hole), [library]), null);
  const science = campus.buildings.find(item => item.id === '444991872');
  assert.equal(pickPlanBuilding(center(science.points), campus.buildings), science.id);
  assert.equal(pickPlanBuilding([4000, 4000], campus.buildings), null);
});
test('比例尺随地图缩放保持米制长度，不依赖像素或设备密度', () => {
  for (const scale of [.22, .54, 1.2, 3.2]) {
    const bar = planScaleBar(scale); assert.equal(bar.pixels, bar.meters * scale);
    assert.ok(bar.pixels > 0 && bar.pixels <= 90);
  }
});
