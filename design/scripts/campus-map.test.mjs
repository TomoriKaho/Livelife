import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { contains, clipRoad, project, origin } from '../src/pages/map/geometry.mjs';
import { activities, venues } from '../src/pages/map/demo.js';
const campus = JSON.parse(await readFile(new URL('../assets/maps/campus.json', import.meta.url), 'utf8'));
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
