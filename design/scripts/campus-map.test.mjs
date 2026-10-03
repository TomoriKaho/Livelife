import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { contains, clipRoad, project, origin, constrainToBoundary } from '../src/pages/map/geometry.mjs';
import { activities, venues, demoLocation } from '../src/pages/map/demo.js';
import { initialView } from '../src/pages/map/view.mjs';
const campus = JSON.parse(await readFile(new URL('../assets/maps/campus.json', import.meta.url), 'utf8'));
test('拖动中心按凹形校界约束，边界及校内位置保持稳定', () => {
  const u = [[0, 0], [10, 0], [10, 10], [7, 10], [7, 3], [3, 3], [3, 10], [0, 10]];
  assert.deepEqual(constrainToBoundary([2, 5], u), [2, 5]);
  assert.deepEqual(constrainToBoundary([5, 6], u), [7, 6]);
  assert.deepEqual(constrainToBoundary([12, 12], u), [10, 10]);
  assert.deepEqual(constrainToBoundary([7, 6], u), [7, 6]);
});
test('初始相机与定位蓝点共用校内位置，视角低于原校园全景', () => {
  assert.deepEqual(initialView.target, [demoLocation[0], 0, demoLocation[1]]);
  assert.ok(contains(demoLocation, campus.boundary));
  assert.ok(initialView.offset[1] < 480);
  assert.ok(Math.hypot(...initialView.offset) < 700);
});
test('周边背景有实际 OSM 建筑与连续道路，不混入校内可交互建筑', () => {
  assert.ok(campus.context.buildings.length > 500);
  const campusIds = new Set(campus.buildings.map(b => b.id));
  assert.ok(campus.context.buildings.every(b => !campusIds.has(b.id)));
  assert.ok(campus.context.roads.some(r => !contains([(r.points[0][0] + r.points[1][0]) / 2, (r.points[0][1] + r.points[1][1]) / 2], campus.boundary)));
});
test('跨界道路保留校内部分，包含起点和终点均在校外的情况', () => {
  const square = [[0, 0], [10, 0], [10, 10], [0, 10]];
  assert.deepEqual(clipRoad([[-5, 5], [15, 5]], square), [[[0, 5], [10, 5]]]);
  assert.deepEqual(clipRoad([[-5, -5], [-1, -1]], square), []);
});
test('凹形校界中的同一路段可产生两个独立校内片段', () => {
  const u = [[0, 0], [10, 0], [10, 10], [7, 10], [7, 3], [3, 3], [3, 10], [0, 10]];
  assert.deepEqual(clipRoad([[-5, 5], [15, 5]], u), [[[0, 5], [3, 5]], [[7, 5], [10, 5]]]);
});
test('北京坐标投影保持原点、米制方向与精度', () => {
  assert.deepEqual(campus.origin, origin);
  assert.deepEqual(project({ lon: origin[0], lat: origin[1] }), [0, -0]);
  const [x, z] = project({ lon: origin[0] + .001, lat: origin[1] + .001 });
  assert.ok(x > 85 && x < 86 && z < -111 && z > -112);
});
test('本地校区资源完整，演示活动映射到实际 OSM 建筑且楼层合法', () => {
  assert.ok(campus.buildings.length > 200);
  assert.ok(campus.water.some(w => w.name === '未名湖'));
  assert.ok(campus.buildings.every(b => b.points.every(p => p.every(Number.isFinite)) && b.height > 0));
  assert.ok(campus.roads.every(r => contains([(r.points[0][0] + r.points[1][0]) / 2, (r.points[0][1] + r.points[1][1]) / 2], campus.boundary)));
  for (const a of activities) {
    assert.ok(campus.buildings.some(b => b.id === a.building));
    const venue = venues.find(v => v.id === a.building);
    assert.ok(venue && a.floor > 0 && a.floor <= venue.floors);
  }
});
