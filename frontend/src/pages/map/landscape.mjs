import * as THREE from 'three';
import { contains } from './geometry.mjs';
import { insideFootprint } from './rings.mjs';
import { footprintShape } from './architecture.mjs';
import { pencilMaterial, pencilEdge } from './pencil-material.mjs';
import { mapPalette } from './map-palette.mjs';

function randomGenerator(seed) {
  return () => { seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0; return seed / 4294967296; };
}
function segmentDistance(p, a, b) {
  const dx = b[0] - a[0], dz = b[1] - a[1], length = dx * dx + dz * dz;
  const t = length ? Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dz) / length)) : 0;
  return Math.hypot(p[0] - a[0] - dx * t, p[1] - a[1] - dz * t);
}
export function treeLayout(campus) {
  const random = randomGenerator(20261003), trees = [], occupied = new Set(), grid = new Map(), cell = 32;
  const insert = (points, item, padding = 0) => {
    const xs = points.map(p => p[0]), zs = points.map(p => p[1]);
    for (let x = Math.floor((Math.min(...xs) - padding) / cell); x <= Math.floor((Math.max(...xs) + padding) / cell); x++)
      for (let z = Math.floor((Math.min(...zs) - padding) / cell); z <= Math.floor((Math.max(...zs) + padding) / cell); z++) {
        const key = `${x},${z}`; if (!grid.has(key)) grid.set(key, []); grid.get(key).push(item);
      }
  };
  for (const b of [...campus.buildings, ...campus.context.buildings]) insert(b.points, { building: b });
  for (const w of [...campus.water, ...campus.context.water]) insert(w.points, { water: w });
  for (const r of campus.context.roads) insert(r.points, { road: r }, r.width / 2 + 2);
  for (const g of [...campus.green, ...campus.context.green].filter(g => g.kind === 'pitch')) insert(g.points, { pitch: g });
  function add(point, source, willow = false) {
    const nearby = grid.get(`${Math.floor(point[0] / cell)},${Math.floor(point[1] / cell)}`) || [];
    if (nearby.some(o => o.building ? insideFootprint(point, o.building) : o.water ? contains(point, o.water.points) : o.pitch ? contains(point, o.pitch.points) : segmentDistance(point, ...o.road.points) < o.road.width / 2 + 2)) return;
    const key = `${Math.round(point[0] / 7)},${Math.round(point[1] / 7)}`;
    if (occupied.has(key)) return; occupied.add(key);
    trees.push({ point, height: 7 + random() * 5, size: 2.5 + random() * 2.1, shade: random(), willow, source });
  }
  for (const tree of campus.trees || []) add(tree.point, 'osm');
  for (const row of campus.treeRows || []) for (let i = 1; i < row.points.length; i++) {
    const a = row.points[i - 1], b = row.points[i], count = Math.floor(Math.hypot(b[0] - a[0], b[1] - a[1]) / 12);
    for (let j = 0; j <= count; j++) { const t = j / Math.max(1, count); add([a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t], 'osm-row'); }
  }
  // 湖岸外侧疏植垂柳，采用同一条真实岸线作分布参照。
  for (const w of campus.water.filter(w => w.name === '未名湖')) for (let i = 1; i < w.points.length; i++) {
    const a = w.points[i - 1], b = w.points[i], length = Math.hypot(b[0] - a[0], b[1] - a[1]);
    const normal = [-(b[1] - a[1]) / length, (b[0] - a[0]) / length];
    const c = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
    if (contains([c[0] + normal[0], c[1] + normal[1]], w.points)) normal.forEach((_, j) => normal[j] *= -1);
    if (i % 2 === 0 && length) add([c[0] + normal[0] * 8, c[1] + normal[1] * 8], 'shore-approximation', true);
  }
  // 固定种子补充绿地树冠，不声称为逐株测绘。院内密、校外疏，留出道路与建筑。
  const xs = campus.context.extent.map(p => p[0]), zs = campus.context.extent.map(p => p[1]);
  const greens = [...campus.green, ...campus.context.green].filter(g => g.kind !== 'pitch');
  for (let x = Math.min(...xs) + 8; x < Math.max(...xs); x += 24) for (let z = Math.min(...zs) + 8; z < Math.max(...zs); z += 24) {
    const point = [x + (random() - .5) * 12, z + (random() - .5) * 12];
    const onGreen = greens.some(g => contains(point, g.points));
    if (random() < (onGreen ? .63 : contains(point, campus.boundary) ? .13 : .025)) add(point, 'landscape-approximation');
  }
  return trees;
}
export function createVegetation(campus) {
  const trees = treeLayout(campus), group = new THREE.Group(), matrix = new THREE.Matrix4(), q = new THREE.Quaternion(), v = new THREE.Vector3(), scale = new THREE.Vector3();
  const trunk = new THREE.InstancedMesh(new THREE.CylinderGeometry(.25, .4, 1, 5), pencilMaterial({ color: '#9e8966', scale: 3 }), trees.length);
  const crowns = new THREE.InstancedMesh(new THREE.IcosahedronGeometry(1, 2), pencilMaterial({ color: '#ffffff', scale: 6 }), trees.length);
  const upper = new THREE.InstancedMesh(new THREE.IcosahedronGeometry(1, 1), pencilMaterial({ color: '#ffffff', scale: 6 }), trees.length);
  const palette = mapPalette.trees;
  trees.forEach((t, i) => {
    const [x, z] = t.point;
    matrix.compose(v.set(x, t.height * .33, z), q, scale.set(1, t.height * .66, 1)); trunk.setMatrixAt(i, matrix);
    q.setFromAxisAngle(new THREE.Vector3(0, 1, 0), t.shade * Math.PI);
    matrix.compose(v.set(x, t.height * .67, z), q, scale.set(t.size, t.willow ? t.size * 1.4 : t.size * .82, t.size)); crowns.setMatrixAt(i, matrix);
    matrix.compose(v.set(x + t.size * .23, t.height * .86, z - t.size * .15), q, scale.set(t.size * .7, t.size * .7, t.size * .72)); upper.setMatrixAt(i, matrix);
    crowns.setColorAt(i, new THREE.Color(palette[Math.floor(t.shade * palette.length)])); upper.setColorAt(i, new THREE.Color(palette[(Math.floor(t.shade * palette.length) + 1) % palette.length]));
    q.identity();
  });
  for (const item of [trunk, crowns, upper]) { item.castShadow = true; item.receiveShadow = true; item.computeBoundingSphere(); group.add(item); }
  // 实例化背面外壳仅描树冠外缘，避免把每个三角面都画成网格。
  for (const item of [crowns, upper]) {
    const outline = new THREE.InstancedMesh(item.geometry.clone().scale(1.022, 1.022, 1.022),
      new THREE.MeshBasicMaterial({ color: '#535e45', side: THREE.BackSide, transparent: true, opacity: .45, depthWrite: false }), trees.length);
    outline.instanceMatrix.copy(item.instanceMatrix); outline.computeBoundingSphere(); group.add(outline);
  }
  group.userData.treeCount = trees.length; return group;
}
export function createWater(w) {
  const group = new THREE.Group(), geometry = new THREE.ShapeGeometry(footprintShape(w.points)); geometry.rotateX(-Math.PI / 2);
  const water = new THREE.Mesh(geometry, pencilMaterial({ color: mapPalette.water, side: THREE.DoubleSide, scale: .6 })); water.position.y = .18; pencilEdge(water, { opacity: .28 }); group.add(water);
  // 岸边窄石带与水面细波纹，均裁到真实湖形，不依赖在线贴图。
  const bank = [], ripples = [], random = randomGenerator(811), xs = w.points.map(p => p[0]), zs = w.points.map(p => p[1]);
  for (let i = 1; i < w.points.length; i++) {
    const a = w.points[i - 1], b = w.points[i], length = Math.hypot(b[0] - a[0], b[1] - a[1]); if (!length) continue;
    const nx = -(b[1] - a[1]) / length * 1.4, nz = (b[0] - a[0]) / length * 1.4;
    const q = [[a[0] + nx, .24, a[1] + nz], [b[0] + nx, .24, b[1] + nz], [b[0] - nx, .24, b[1] - nz], [a[0] - nx, .24, a[1] - nz]];
    [0, 1, 2, 0, 2, 3].forEach(j => bank.push(...q[j]));
  }
  for (let x = Math.min(...xs) + 8; x < Math.max(...xs); x += 9) for (let z = Math.min(...zs) + 6; z < Math.max(...zs); z += 12) {
    const length = 2 + random() * 6, zz = z + random() * 7;
    if (contains([x, zz], w.points) && contains([x + length, zz + .6], w.points)) ripples.push(x, .205, zz, x + length, .205, zz + .6);
  }
  const bg = new THREE.BufferGeometry(); bg.setAttribute('position', new THREE.Float32BufferAttribute(bank, 3)); bg.computeVertexNormals();
  const shore = new THREE.Mesh(bg, pencilMaterial({ color: '#c9c6a6', side: THREE.DoubleSide })); shore.receiveShadow = true; group.add(shore);
  const rg = new THREE.BufferGeometry(); rg.setAttribute('position', new THREE.Float32BufferAttribute(ripples, 3));
  group.add(new THREE.LineSegments(rg, new THREE.LineBasicMaterial({ color: '#a8c6b4', transparent: true, opacity: .2 })));
  return group;
}
