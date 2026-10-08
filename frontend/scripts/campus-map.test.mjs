import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { contains, clipRoad, project, origin, constrainToBoundary } from '../src/pages/map/geometry.mjs';
import { activities, venues, demoLocation } from '../src/pages/map/demo.js';
import { initialView } from '../src/pages/map/view.mjs';
import { joinRings, insideFootprint } from '../src/pages/map/rings.mjs';
import { createBuilding, extrudeFootprint, profileFor } from '../src/pages/map/architecture.mjs';
import { treeLayout } from '../src/pages/map/landscape.mjs';
import * as THREE from 'three';
import { prepareStoreys, sliceGeometry, transitionModel, animateModel, storeysInput, buildStoreysData, applyStoreysData, storeysBuffers } from '../src/pages/map/storeys.mjs';
const campus = JSON.parse(await readFile(new URL('../src/assets/maps/campus.json', import.meta.url), 'utf8'));
test('多面建筑拼接反向成员并保留开放折线失败状态', () => {
  const segments = [[[0, 0], [10, 0]], [[0, 10], [10, 10]], [[10, 0], [10, 10]], [[0, 10], [0, 0]]];
  const rings = joinRings(segments);
  assert.equal(rings.length, 1); assert.deepEqual(rings[0][0], rings[0].at(-1));
  assert.equal(joinRings([[[0, 0], [10, 0], [10, 10]]]).length, 0);
});
test('图书馆补充数据保留庭院，挤出顶面不覆盖内部空洞', () => {
  const b = campus.buildings.find(b => b.id === 'r3249649');
  assert.equal(b.name, '北京大学图书馆'); assert.equal(b.holes.length, 3);
  const g = extrudeFootprint(b, 23), p = g.attributes.position;
  for (let i = 0; i < p.count; i += 3) {
    if ([0, 1, 2].every(k => Math.abs(p.getY(i + k) - 23) < .001)) {
      const c = [0, 1, 2].reduce((sum, k) => [sum[0] + p.getX(i + k) / 3, sum[1] + p.getZ(i + k) / 3], [0, 0]);
      assert.ok(!b.holes.some(h => contains(c, h)), '顶面不能填满庭院');
    }
  }
  g.dispose();
});
test('所有精细建筑几何有效且模型部件保留可点击的 OSM 标识', () => {
  for (const b of campus.buildings) {
    const model = createBuilding(b);
    model.traverse(o => {
      if (!o.isMesh) return;
      assert.equal(o.userData.building, b.id);
      assert.ok(o.geometry.attributes.position.array.every(Number.isFinite), `建筑 ${b.id} 几何出现非有限坐标`);
      o.geometry.dispose(); o.material.dispose();
    });
  }
});

test('真实建筑预先按层裁切，分层前后复用原屋顶及几何，反向动画保持连续', () => {
  const b = campus.buildings.find(b => b.id === '444991872'), model = createBuilding(b);
  const roof = model.children.find(o => o.userData.role === 'roof');
  prepareStoreys(model, b, 4);
  const levels = model.userData.storeys, shells = levels.map(l => l.userData.shell), geometries = shells.map(s => s.geometry), materials = shells.map(s => s.material);
  const bases = levels.map(l => l.position.y);
  levels.forEach((l, i) => { l.userData.lift = i * 30; }); roof.userData.lift = 120;
  transitionModel(model, 1, 100, 1000); animateModel(model, 500);
  const halfway = levels.map(l => l.position.y);
  assert.ok(model.userData.progress > 0 && model.userData.progress < 1);
  transitionModel(model, 0, 500, 1000); animateModel(model, 500);
  assert.deepEqual(levels.map(l => l.position.y), halfway, '反向第一帧须接住当前坐标');
  animateModel(model, 1500);
  assert.deepEqual(levels.map(l => l.position.y), bases); assert.equal(roof.position.y, model.userData.profile.height);
  for (let round = 0; round < 3; round++) {
    transitionModel(model, 1, 2000, 0); animateModel(model, 2000);
    transitionModel(model, 0, 2001, 0); animateModel(model, 2001);
  }
  assert.equal(model.userData.parts.at(-1), roof);
  levels.forEach((l, i) => { assert.equal(l.userData.shell, shells[i]); assert.equal(shells[i].geometry, geometries[i]); assert.equal(shells[i].material, materials[i]); });
  assert.equal(prepareStoreys(model, b, 4), model); assert.equal(model.userData.storeys, levels);
});

test('水平裁切插值颜色、法线并保持表面积，跨层长窗不丢失或重复', () => {
  const g = new THREE.PlaneGeometry(8, 10).toNonIndexed(); g.translate(0, 5, 0);
  const material = new THREE.MeshBasicMaterial({ color: '#6598c2' }), matrix = new THREE.Matrix4();
  const area = geometry => {
    const p = geometry.attributes.position, a = new THREE.Vector3(), b = new THREE.Vector3(), c = new THREE.Vector3(); let sum = 0;
    for (let i = 0; i < p.count; i += 3) sum += b.fromBufferAttribute(p, i + 1).sub(a.fromBufferAttribute(p, i)).cross(c.fromBufferAttribute(p, i + 2).sub(a)).length() / 2;
    return sum;
  };
  let total = 0;
  for (let i = 0; i < 4; i++) {
    const slice = sliceGeometry(g, matrix, material, i * 2.5, (i + 1) * 2.5);
    assert.ok(slice.attributes.position.array.every(Number.isFinite));
    const p = slice.attributes.position;
    for (let j = 0; j < p.count; j++) { assert.ok(p.getY(j) >= -1e-5 && p.getY(j) <= 2.50001); assert.ok(Math.abs(slice.attributes.color.getX(j) - material.color.r) < 1e-6); }
    total += area(slice); slice.dispose();
  }
  assert.ok(Math.abs(total - area(g)) < .0001); g.dispose(); material.dispose();
});

test('裁切后的图书馆楼层不填庭院，顶层去重顶盖但保留原屋顶', () => {
  const b = campus.buildings.find(b => b.id === 'r3249649'), model = prepareStoreys(createBuilding(b), b, 5);
  for (const level of model.userData.storeys) {
    const p = level.userData.shell.geometry.attributes.position, n = level.userData.shell.geometry.attributes.normal;
    for (let i = 0; i < p.count; i += 3) {
      if ([0, 1, 2].every(k => Math.abs(n.getY(i + k)) > .99)) {
        const c = [0, 1, 2].reduce((sum, k) => [sum[0] + p.getX(i + k) / 3, sum[1] + p.getZ(i + k) / 3], [0, 0]);
        assert.ok(!b.holes.some(h => contains(c, h)));
      }
    }
  }
  const top = model.userData.storeys.at(-1).userData.shell.geometry.attributes.normal;
  assert.ok(!Array.from({length:top.count}, (_, i) => top.getY(i)).some(y => y > .99));
  assert.ok(model.userData.parts.some(p => p.userData.role === 'roof'));
});

test('全校可选建筑提前准备楼层，单层/地标保持合法模型且无需运行时重建', () => {
  for (const b of campus.buildings) {
    const model = createBuilding(b), count = venues.find(v => v.id === b.id)?.floors || Math.min(6, model.userData.profile.floors);
    prepareStoreys(model, b, count);
    if (model.userData.profile.scenic) { assert.equal(model.userData.storeys, undefined); continue; }
    assert.equal(model.userData.storeys.length, count);
    model.traverse(o => {
      if (!o.isMesh) return;
      assert.equal(o.userData.building, b.id);
      assert.ok(o.geometry.attributes.position.array.every(Number.isFinite));
      assert.equal(o.material.userData.pencil, true);
    });
  }
});
test('固定树木布局可复现，树干不生在建筑或水面上', () => {
  const trees = treeLayout(campus);
  assert.ok(trees.length > 500);
  assert.deepEqual(trees, treeLayout(campus));
  for (const tree of trees) {
    assert.ok(![...campus.buildings, ...campus.context.buildings].some(b => insideFootprint(tree.point, b)));
    assert.ok(![...campus.water, ...campus.context.water].some(w => contains(tree.point, w.points)));
  }
});
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
    if (!a.building) {
      assert.equal(a.mapPosition?.length, 2, a.title);
      assert.ok(a.mapPosition.every(Number.isFinite), a.title);
      continue;
    }
    const building = campus.buildings.find(b => b.id === a.building);
    assert.ok(building, a.title);
    const venue = venues.find(v => v.id === a.building);
    const floors = venue?.floors || Math.min(6, profileFor(building).floors);
    assert.ok(a.floor > 0 && a.floor <= floors, a.title);
  }
});


test('Worker 楼层缓冲区往返保留庭院、颜色、勾线及原屋顶，输入传输不分离现场模型', () => {
  for (const id of ['r3249649', '444991872']) {
    const building = campus.buildings.find(b => b.id === id);
    const reference = prepareStoreys(createBuilding(building), building, 4);
    const model = createBuilding(building), roof = model.children.find(o => o.userData.role === 'roof');
    const live = model.children.find(o => o.isMesh).geometry.attributes.position.array;
    const input = storeysInput(model, building, 4);
    const transferred = structuredClone(input, { transfer: storeysBuffers(input) });
    assert.ok(live.byteLength > 0, '传输的是副本，不能分离现场几何');
    const data = buildStoreysData(transferred);
    applyStoreysData(model, building, structuredClone(data, { transfer: storeysBuffers(data) }));
    assert.equal(model.userData.parts.at(-1), roof);
    for (const [index, level] of model.userData.storeys.entries()) {
      const shell = level.userData.shell, expected = reference.userData.storeys[index].userData.shell;
      for (const name of ['position', 'normal', 'color'])
        assert.deepEqual(shell.geometry.attributes[name].array, expected.geometry.attributes[name].array);
      assert.deepEqual(shell.children[0].geometry.attributes.position.array, expected.children[0].geometry.attributes.position.array);
      assert.equal(shell.userData.building, id);
      assert.equal(shell.userData.floor, index + 1);
    }
    for (const group of [model, reference]) group.traverse(o => { o.geometry?.dispose(); o.material?.dispose(); });
  }
});
