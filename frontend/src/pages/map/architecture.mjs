import * as THREE from 'three';
import { center } from './geometry.mjs';
import { insideFootprint } from './rings.mjs';
import { pencilMaterial, pencilEdge } from './pencil-material.mjs';

import { profileFor } from './model-profiles.mjs';
export { profileFor } from './model-profiles.mjs';

export function footprintShape(points, holes = []) {
  const s = new THREE.Shape(points.map(([x, z]) => new THREE.Vector2(x, -z)));
  s.holes = holes.map(ring => new THREE.Path(ring.map(([x, z]) => new THREE.Vector2(x, -z))));
  return s;
}
export function extrudeFootprint(b, depth) {
  const geometry = new THREE.ExtrudeGeometry(footprintShape(b.points, b.holes), { depth, bevelEnabled: false, steps: 1, curveSegments: 1 });
  geometry.rotateX(-Math.PI / 2); return geometry;
}
function buffer(vertices) {
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3)); g.computeVertexNormals(); return g;
}
function mesh(group, geometry, color, y = 0, options = {}) {
  const { roughness, metalness, ...matteOptions } = options;
  const m = new THREE.Mesh(geometry, pencilMaterial({ color, ...matteOptions }));
  m.position.y = y; m.castShadow = true; m.receiveShadow = true; group.add(m); return m;
}
function bounds(points) {
  return { minX: Math.min(...points.map(p => p[0])), maxX: Math.max(...points.map(p => p[0])), minZ: Math.min(...points.map(p => p[1])), maxZ: Math.max(...points.map(p => p[1])) };
}
function distanceToRing(p, ring) {
  let best = Infinity;
  for (let i = 1; i < ring.length; i++) {
    const a = ring[i - 1], b = ring[i], dx = b[0] - a[0], dz = b[1] - a[1], sq = dx * dx + dz * dz;
    const t = sq ? Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dz) / sq)) : 0;
    best = Math.min(best, Math.hypot(p[0] - a[0] - dx * t, p[1] - a[1] - dz * t));
  }
  return best;
}
// 按轮廓（含庭院）生成收坡屋顶。细分三角面使内部顶点抬起，避免只有边界点的“平屋顶”。
function pitchedRoof(b, rise) {
  const base = new THREE.ShapeGeometry(footprintShape(b.points, b.holes)), positions = base.attributes.position, vertices = [];
  const rings = [b.points, ...(b.holes || [])], { minX, maxX, minZ, maxZ } = bounds(b.points);
  const run = Math.max(2, Math.min(maxX - minX, maxZ - minZ) * .25);
  const at = p => [p[0], Math.min(1, Math.min(...rings.map(r => distanceToRing(p, r))) / run) * rise, p[1]];
  const mid = (a, c) => [(a[0] + c[0]) / 2, (a[1] + c[1]) / 2];
  function subdivide(a, c, d, depth) {
    if (!depth) { vertices.push(...at(a), ...at(c), ...at(d)); return; }
    const ac = mid(a, c), cd = mid(c, d), da = mid(d, a);
    subdivide(a, ac, da, depth - 1); subdivide(ac, c, cd, depth - 1); subdivide(da, cd, d, depth - 1); subdivide(ac, cd, da, depth - 1);
  }
  for (let i = 0; i < base.index.count; i += 3) {
    const p = [0, 1, 2].map(k => { const j = base.index.getX(i + k); return [positions.getX(j), -positions.getY(j)]; });
    subdivide(...p, 2);
  }
  base.dispose(); return buffer(vertices);
}
function facade(b, p) {
  const windows = [], trim = [], frames = [];
  const quad = (array, a, d, normal, along, left, right, bottom, top, offset) => {
    const at = (t, y) => [a[0] + along[0] * t + normal[0] * offset, y, a[1] + along[1] * t + normal[1] * offset];
    const q = [at(left, bottom), at(right, bottom), at(right, top), at(left, top)];
    [0, 1, 2, 0, 2, 3].forEach(i => array.push(...q[i]));
  };
  for (const ring of [b.points, ...(b.holes || [])]) {
    for (let i = 1; i < ring.length; i++) {
      const a = ring[i - 1], d = ring[i], length = Math.hypot(d[0] - a[0], d[1] - a[1]);
      if (length < 2.8) continue;
      const along = [(d[0] - a[0]) / length, (d[1] - a[1]) / length]; let normal = [-along[1], along[0]];
      if (insideFootprint([(a[0] + d[0]) / 2 + normal[0] * .2, (a[1] + d[1]) / 2 + normal[1] * .2], b)) normal = normal.map(v => -v);
      const floors = Math.min(12, p.floors), pitch = p.height / floors;
      if (p.style === 'science' && length > 30) {
        const cols = Math.max(2, Math.floor(length / 4.4));
        for (let c = 0; c < cols; c++) {
          const t = (c + .5) * length / cols, w = c % 3 === 1 ? 1.9 : .85;
          quad(frames, a, d, normal, along, t - w / 2 - .1, t + w / 2 + .1, .8, p.height - 3.7, .08);
          quad(windows, a, d, normal, along, t - w / 2, t + w / 2, .95, p.height - 3.85, .12);
          for (let f = 1; f < floors - 1; f++) quad(trim, a, d, normal, along, t - w / 2, t + w / 2, f * pitch, f * pitch + .12, .15);
        }
        // 实景顶部连续玻璃带，与下部灰砖上的细长竖窗区分。
        quad(windows, a, d, normal, along, .6, length - .6, p.height - 3.1, p.height - .4, .12);
        for (let x = 1; x < length; x += 3.2) quad(trim, a, d, normal, along, x, x + .15, p.height - 3.1, p.height - .4, .16);
        // 最长立面上的中央玻璃入口，位置是模型近似而非入口测绘。
        if (length > 60) {
          const left = length * .38, right = length * .62;
          quad(windows, a, d, normal, along, left, right, .8, p.height - .6, .2);
          for (let x = left; x < right; x += 2.2) quad(trim, a, d, normal, along, x, x + .12, .8, p.height - .6, .25);
          for (let f = 1; f < floors; f++) quad(trim, a, d, normal, along, left, right, f * pitch, f * pitch + .12, .25);
        }
        continue;
      }
      const cols = Math.max(1, Math.floor(length / (p.style === 'science' ? 3 : 4.2))), spacing = length / cols;
      for (let f = 0; f < floors; f++) {
        const bottom = f * pitch + pitch * .3, top = Math.min(p.height - .5, bottom + pitch * .48);
        for (let c = 0; c < cols; c++) {
          const left = c * spacing + spacing * .2, right = (c + 1) * spacing - spacing * .2;
          quad(frames, a, d, normal, along, left - .14, right + .14, bottom - .15, top + .15, .08);
          quad(windows, a, d, normal, along, left, right, bottom, top, .12);
          const middle = (left + right) / 2;
          quad(trim, a, d, normal, along, middle - .045, middle + .045, bottom, top, .15);
          quad(trim, a, d, normal, along, left, right, bottom + (top - bottom) * .55, bottom + (top - bottom) * .55 + .07, .15);
        }
        if (p.style !== 'traditional') quad(trim, a, d, normal, along, 0, length, (f + 1) * pitch - .32, (f + 1) * pitch - .1, .12);
      }
      quad(trim, a, d, normal, along, 0, length, .05, .6, .13);
    }
  }
  return { windows, trim, frames };
}
export function createRoof(b, p = profileFor(b)) {
  const group = new THREE.Group();
  group.userData.role = 'roof';
  const pitched = ['traditional', 'gate', 'hall', 'library'].includes(p.style);
  if (pitched) {
    mesh(group, extrudeFootprint(b, .55), p.roof, 0);
    mesh(group, pitchedRoof(b, p.roofRise || (p.style === 'library' ? 5 : 3.8)), p.roof, .55, { side: THREE.DoubleSide });
    const eaves = [];
    for (const ring of [b.points, ...(b.holes || [])]) for (let i = 1; i < ring.length; i++) {
      const a = ring[i - 1], d = ring[i], length = Math.hypot(d[0] - a[0], d[1] - a[1]); if (!length) continue;
      let nx = -(d[1] - a[1]) / length, nz = (d[0] - a[0]) / length;
      if (insideFootprint([(a[0] + d[0]) / 2 + nx * .2, (a[1] + d[1]) / 2 + nz * .2], b)) { nx *= -1; nz *= -1; }
      const q = [[a[0], .55, a[1]], [d[0], .55, d[1]], [d[0] + nx * .9, .3, d[1] + nz * .9], [a[0] + nx * .9, .3, a[1] + nz * .9]];
      [0, 1, 2, 0, 2, 3].forEach(j => eaves.push(...q[j]));
    }
    mesh(group, buffer(eaves), p.roof, 0, { side: THREE.DoubleSide });
  } else if (p.style === 'gym') {
    const { minX, maxX, minZ, maxZ } = bounds(b.points), vertices = [], nx = 24;
    for (let i = 0; i < nx; i++) {
      const a = minX + (maxX - minX) * i / nx, d = minX + (maxX - minX) * (i + 1) / nx;
      const y = x => 1 + Math.sin((x - minX) / (maxX - minX) * Math.PI) * 7;
      [[a, y(a), minZ], [d, y(d), minZ], [d, y(d), maxZ], [a, y(a), minZ], [d, y(d), maxZ], [a, y(a), maxZ]].forEach(v => vertices.push(...v));
    }
    mesh(group, buffer(vertices), p.roof, 0, { side: THREE.DoubleSide, metalness: .25, roughness: .5 });
  } else {
    mesh(group, extrudeFootprint(b, .65), p.roof);
    // 凹轮廓、庭院边缘均保留女儿墙，不跨院补成一个矩形。
    const vertices = [];
    for (const ring of [b.points, ...(b.holes || [])]) for (let i = 1; i < ring.length; i++) {
      const a = ring[i - 1], d = ring[i];
      [[a[0], 0, a[1]], [d[0], 0, d[1]], [d[0], 1.25, d[1]], [a[0], 0, a[1]], [d[0], 1.25, d[1]], [a[0], 1.25, a[1]]].forEach(v => vertices.push(...v));
    }
    mesh(group, buffer(vertices), p.wall, 0, { side: THREE.DoubleSide });
    const c = center(b.points);
    if (insideFootprint(c, b)) {
      const size = Math.min(7, Math.sqrt(Math.abs((bounds(b.points).maxX - bounds(b.points).minX) * (bounds(b.points).maxZ - bounds(b.points).minZ))) / 8);
      const plant = mesh(group, new THREE.BoxGeometry(size, 1.5, size * .7), '#a0a7a0', 1.2); plant.position.x = c[0]; plant.position.z = c[1];
    }
    if (p.style === 'science') {
      const { minX, maxX, minZ, maxZ } = bounds(b.points), middle = (minX + maxX) / 2;
      for (const side of [-1, 1]) {
        // 左右平屋檐稍抬高，中部低屋顶，表达理教玻璃入口两翼的体量。
        const width = (maxX - minX) * .38, x = middle + side * (maxX - minX) * .31;
        const canopy = mesh(group, new THREE.BoxGeometry(width, .32, maxZ - minZ), p.roof); canopy.position.set(x, 1.4, (minZ + maxZ) / 2);
      }
    }
  }
  return group;
}
function pagoda(b, p) {
  const group = new THREE.Group(), [cx, cz] = center(b.points), { minX, maxX, minZ, maxZ } = bounds(b.points);
  const radius = Math.min(maxX - minX, maxZ - minZ) / 2;
  const column = (bottom, top, h, y, color) => {
    const m = mesh(group, new THREE.CylinderGeometry(top, bottom, h, 8, 1), color); m.position.set(cx, y + h / 2, cz); m.rotation.y = Math.PI / 8; return m;
  };
  column(radius * 1.12, radius * 1.12, 1.2, 0, '#9d9c89');
  column(radius * .89, radius * .84, 9.2, 1.2, p.wall);
  // 下层塔身较高，上方十三重密檐逐次收分，合计高度约 37m。
  for (let i = 0; i < 13; i++) {
    const r = radius * (.88 - i * .036), y = 10.4 + i * 1.78;
    column(r * .96, r * .89, 1.78, y, p.wall);
    column(r * 1.27, r * 1.27, .28, y, '#4e584c');
    column(r * 1.27, r * .82, .85, y + .28, p.roof);
    column(r * 1.02, r * .98, .22, y + 1.12, '#a3977d');
    // 八面窗洞与灰色窗框。
    for (let side = 0; side < 8; side++) {
      const angle = side * Math.PI / 4;
      const opening = mesh(group, new THREE.PlaneGeometry(.6, .7), p.glass, 0, { side: THREE.DoubleSide });
      opening.position.set(cx + Math.sin(angle) * r * .925, y + 1.5, cz + Math.cos(angle) * r * .925); opening.rotation.y = angle;
    }
  }
  column(radius * .42, .15, 2.4, 33.6, p.roof);
  column(.32, .12, 1, 36, '#8b8064');
  const door = mesh(group, new THREE.PlaneGeometry(1.7, 3.5), '#4e4839', 0, { side: THREE.DoubleSide }); door.position.set(cx, 2.9, cz + radius * .84);
  return group;
}
function gate(b, p) {
  const group = new THREE.Group(), { minX, maxX, minZ, maxZ } = bounds(b.points), [cx, cz] = center(b.points);
  const span = maxZ - minZ, depth = Math.min(5, maxX - minX);
  for (let i = 0; i < 4; i++) {
    const post = mesh(group, new THREE.BoxGeometry(depth, p.height, 1.8), p.wall);
    post.position.set(cx, p.height / 2, minZ + .9 + (span - 1.8) * i / 3);
  }
  const lintel = mesh(group, new THREE.BoxGeometry(depth, .85, span), p.wall); lintel.position.set(cx, p.height - .4, cz);
  const roof = createRoof(b, p); roof.position.y = p.height; group.add(roof);
  const plaque = mesh(group, new THREE.PlaneGeometry(span * .36, .85), '#eee5cc', 0, { side: THREE.DoubleSide });
  plaque.position.set(cx - depth / 2 - .05, p.height - .4, cz); plaque.rotation.y = -Math.PI / 2;
  if (typeof document !== 'undefined') {
    const canvas = document.createElement('canvas'); canvas.width = 512; canvas.height = 96;
    const ctx = canvas.getContext('2d'); ctx.fillStyle = '#eee5cc'; ctx.fillRect(0, 0, 512, 96);
    ctx.fillStyle = '#473e32'; ctx.font = '68px Xiaolai, serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText('北京大学', 256, 48);
    const texture = new THREE.CanvasTexture(canvas); texture.colorSpace = THREE.SRGBColorSpace; plaque.material.map = texture;
  }
  return group;
}
export function createBuilding(b) {
  const p = profileFor(b), group = p.style === 'pagoda' ? pagoda(b, p) : p.style === 'gate' ? gate(b, p) : new THREE.Group();
  if (!['pagoda', 'gate'].includes(p.style)) {
    mesh(group, extrudeFootprint(b, p.height), p.wall);
    const parts = facade(b, p);
    if (parts.frames.length) {
      const g = buffer([...parts.frames, ...parts.trim]), colors = [];
      for (const [vertices, color] of [[parts.frames, p.style === 'traditional' ? '#734c37' : '#dad2bc'], [parts.trim, p.style === 'traditional' ? '#865238' : '#cfc8b8']]) {
        const c = new THREE.Color(color); for (let i = 0; i < vertices.length / 3; i++) colors.push(c.r, c.g, c.b);
      }
      g.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3)); mesh(group, g, '#ffffff', 0, { vertexColors: true, side: THREE.DoubleSide });
    }
    if (parts.windows.length) mesh(group, buffer(parts.windows), p.glass, 0, { roughness: .3, metalness: .28, side: THREE.DoubleSide });
    const roof = createRoof(b, p); roof.position.y = p.height; group.add(roof);
    if (['science', 'library', 'hall', 'teaching'].includes(p.style)) {
      // 沿最长朝南立面放置台阶和门廊，避开庭院；位置是展示近似。
      const faces = b.points.slice(1).map((d, i) => ({ a: b.points[i], d, length: Math.hypot(d[0] - b.points[i][0], d[1] - b.points[i][1]) })).sort((a, d) => d.length - a.length);
      const face = faces[0], a = face.a, d = face.d, c = [(a[0] + d[0]) / 2, (a[1] + d[1]) / 2], angle = -Math.atan2(d[1] - a[1], d[0] - a[0]);
      const porch = new THREE.Group(); porch.position.set(c[0], 0, c[1]); porch.rotation.y = angle;
      let outward = 1; if (insideFootprint([c[0] + Math.sin(angle) * 2, c[1] + Math.cos(angle) * 2], b)) outward = -1;
      for (let i = 0; i < 4; i++) { const stair = mesh(porch, new THREE.BoxGeometry(Math.min(18, face.length * .35), .28, 4 - i * .65), '#b7b8a9'); stair.position.set(0, .15 + i * .28, outward * (2 - i * .2)); }
      const canopy = mesh(porch, new THREE.BoxGeometry(Math.min(19, face.length * .37), .28, 4.8), p.roof); canopy.position.set(0, 4.8, outward * 1.8);
      group.add(porch);
    }
  }
  // 主要实体的轻勾线；楼体外壳在按层裁切后统一勾线，避免两重轮廓。
  const outlined = [];
  group.traverse(o => { if (o.isMesh) { o.userData.building = b.id; if (o.parent !== group || p.scenic) outlined.push(o); } });
  outlined.forEach(o => pencilEdge(o, { opacity: .5, threshold: 42 }));
  group.userData.profile = p; return group;
}
