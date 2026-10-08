import * as THREE from 'three';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import { pencilMaterial, pencilEdge } from './pencil-material.mjs';

// 水平裁切三角面，插值法线与顶点颜色。庭院仍来自原几何，不按包围盒重建。
export function sliceGeometry(geometry, matrix, material, bottom, top, openTop = false) {
  const positions = [], normals = [], colors = [], p = geometry.attributes.position, n = geometry.attributes.normal, c = geometry.attributes.color;
  const normalMatrix = new THREE.Matrix3().getNormalMatrix(matrix), tint = material.color;
  const vertex = i => {
    const point = new THREE.Vector3().fromBufferAttribute(p, i).applyMatrix4(matrix);
    const normal = new THREE.Vector3().fromBufferAttribute(n, i).applyMatrix3(normalMatrix).normalize();
    const color = c ? new THREE.Color().fromBufferAttribute(c, i).multiply(tint) : tint.clone();
    return [...point.toArray(), ...normal.toArray(), color.r, color.g, color.b];
  };
  const clip = (poly, y, above) => {
    const out = [];
    for (let i = 0; i < poly.length; i++) {
      const a = poly[i], b = poly[(i + 1) % poly.length], insideA = above ? a[1] >= y : a[1] <= y, insideB = above ? b[1] >= y : b[1] <= y;
      if (insideA) out.push(a);
      if (insideA !== insideB) { const t = (y - a[1]) / (b[1] - a[1]); out.push(a.map((v, k) => v + (b[k] - v) * t)); }
    }
    return out;
  };
  const count = geometry.index?.count || p.count;
  for (let i = 0; i < count; i += 3) {
    const indices = [0, 1, 2].map(k => geometry.index ? geometry.index.getX(i + k) : i + k), e = matrix.elements;
    // 先剔除不相交的三角面，避免对每层重复转换整栋窗格的属性。
    const ys = indices.map(j => e[1] * p.getX(j) + e[5] * p.getY(j) + e[9] * p.getZ(j) + e[13]);
    if (Math.min(...ys) > top || Math.max(...ys) < bottom) continue;
    const triangle = indices.map(vertex);
    // 完整模型已有独立屋顶。去掉其下重复的挤出顶盖，顶层展开后才看得到室内。
    if (openTop && triangle.every(v => Math.abs(v[1] - top) < 1e-5 && v[4] > .99)) continue;
    // 共面顶面/底面只交给一个楼层，避免层缝重复绘制。
    if (bottom > 0 && triangle.every(v => Math.abs(v[1] - bottom) < 1e-5)) continue;
    const poly = clip(clip(triangle, bottom, true), top, false);
    for (let j = 1; j < poly.length - 1; j++) {
      const tri = [poly[0], poly[j], poly[j + 1]], a = new THREE.Vector3(...tri[0].slice(0, 3)), b = new THREE.Vector3(...tri[1].slice(0, 3)), d = new THREE.Vector3(...tri[2].slice(0, 3));
      if (b.sub(a).cross(d.sub(a)).lengthSq() < 1e-12) continue;
      for (const v of tri) { positions.push(v[0], v[1] - bottom, v[2]); normals.push(...v.slice(3, 6)); colors.push(...v.slice(6, 9)); }
    }
  }
  if (!positions.length) return null;
  const result = new THREE.BufferGeometry();
  result.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  result.setAttribute('normal', new THREE.Float32BufferAttribute(normals, 3));
  result.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3)); return result;
}

export function prepareStoreys(model, building, count) {
  if (model.userData.storeys || model.userData.profile.scenic) return model;
  const height = model.userData.profile.height, sources = model.children.filter(o => o.isMesh && !o.material.map);
  const storeys = [];
  for (let i = 0; i < count; i++) {
    const baseY = i * height / count, slices = [];
    try {
      for (const source of sources) {
        source.updateMatrix(); const geometry = sliceGeometry(source.geometry, source.matrix, source.material, baseY, (i + 1) * height / count, i === count - 1);
        if (geometry) slices.push(geometry);
      }
      const level = new THREE.Group(); level.position.y = baseY;
      level.userData = { floor: i + 1, baseY, interior: null };
      if (slices.length) {
        const shell = new THREE.Mesh(mergeGeometries(slices), pencilMaterial({ vertexColors: true, side: THREE.DoubleSide }));
        shell.userData = { building: building.id, floor: i + 1 }; shell.castShadow = shell.receiveShadow = true;
        pencilEdge(shell, { opacity: .43, threshold: 40 }); level.add(shell); level.userData.shell = shell;
      }
      model.add(level); storeys.push(level);
    } finally { slices.forEach(g => g.dispose()); }
  }
  finishStoreys(model, sources, storeys, height);
  return model;
}

// 动画从当前进度出发，快速返回/重选也不会跳回动画首帧。
export function transitionModel(model, target, now, duration = 1050) {
  model.userData.transition = { from: model.userData.progress || 0, to: target, start: now, duration };
}
export function animateModel(model, now) {
  const data = model.userData, transition = data.transition;
  if (!transition) return false;
  const t = transition.duration ? Math.min(1, Math.max(0, (now - transition.start) / transition.duration)) : 1;
  const ease = t * t * (3 - 2 * t), progress = transition.from + (transition.to - transition.from) * ease;
  data.progress = progress;
  for (const part of data.parts) {
    part.position.y = part.userData.baseY + (part.userData.lift || 0) * progress;
    const interior = part.userData.interior;
    if (interior) {
      interior.visible = progress > .001;
      interior.traverse(o => { if (o.isMesh) o.material.opacity = Math.min(1, progress * 2); if (o.isLineSegments) o.material.opacity = .4 * Math.min(1, progress * 2); });
    }
  }
  if (t === 1) data.transition = null;
  return true;
}

function finishStoreys(model, sources, storeys, height) {
  const count = storeys.length;
  sources.forEach(source => { source.removeFromParent(); source.geometry.dispose(); source.material.dispose(); });
  // 西门牌匾含本地文字贴图，保留原对象与材质并随所在层移动。
  for (const attachment of model.children.filter(o => o.isMesh && o.material.map)) {
    const i = Math.min(count - 1, Math.max(0, Math.floor(attachment.position.y / (height / count))));
    attachment.position.y -= storeys[i].userData.baseY;
    attachment.userData.floor = i + 1; storeys[i].add(attachment);
  }
  const roof = model.children.find(o => o.userData.role === 'roof');
  model.userData.storeys = storeys;
  model.userData.parts = [...storeys, ...(roof ? [roof] : [])];
  if (roof) roof.userData.baseY = roof.position.y;
  model.userData.progress = 0;
}

// Transfer only copied geometry buffers; live scene resources stay on the UI thread.
function geometryData(geometry, copy = false) {
  const attributes = Object.fromEntries(Object.entries(geometry.attributes).map(([name, attr]) =>
    [name, { array: copy ? attr.array.slice() : attr.array, itemSize: attr.itemSize, normalized: attr.normalized }]));
  return { attributes, index: geometry.index ? (copy ? geometry.index.array.slice() : geometry.index.array) : null };
}
function fromGeometryData(data) {
  const geometry = new THREE.BufferGeometry();
  for (const [name, attr] of Object.entries(data.attributes))
    geometry.setAttribute(name, new THREE.BufferAttribute(attr.array, attr.itemSize, attr.normalized));
  if (data.index) geometry.setIndex(new THREE.BufferAttribute(data.index, 1));
  return geometry;
}
export function storeysInput(model, building, count) {
  const sources = model.children.filter(o => o.isMesh && !o.material.map);
  return { height: model.userData.profile.height, building: building.id, count,
    sources: sources.map(source => { source.updateMatrix(); return {
      geometry: geometryData(source.geometry, true), matrix: source.matrix.toArray(), color: source.material.color.toArray(),
    }; }) };
}
export function storeysBuffers(data) {
  const buffers = new Set();
  function visit(value) {
    if (ArrayBuffer.isView(value)) buffers.add(value.buffer);
    else if (value && typeof value === 'object') Object.values(value).forEach(visit);
  }
  visit(data); return [...buffers];
}
export function buildStoreysData(input) {
  const model = new THREE.Group(); model.userData.profile = { height: input.height };
  for (const source of input.sources) {
    const mesh = new THREE.Mesh(fromGeometryData(source.geometry), new THREE.MeshBasicMaterial({ color: new THREE.Color().fromArray(source.color) }));
    mesh.matrix.fromArray(source.matrix); mesh.matrix.decompose(mesh.position, mesh.quaternion, mesh.scale); model.add(mesh);
  }
  prepareStoreys(model, { id: input.building }, input.count);
  const result = model.userData.storeys.map(level => ({ baseY: level.userData.baseY,
    shell: level.userData.shell ? geometryData(level.userData.shell.geometry) : null,
    edges: level.userData.shell ? geometryData(level.userData.shell.children[0].geometry) : null }));
  model.traverse(o => { o.geometry?.dispose(); o.material?.dispose(); });
  return result;
}
export function applyStoreysData(model, building, data) {
  const sources = model.children.filter(o => o.isMesh && !o.material.map);
  const storeys = data.map((item, index) => {
    const level = new THREE.Group(); level.position.y = item.baseY;
    level.userData = { floor: index + 1, baseY: item.baseY, interior: null };
    if (item.shell) {
      const shell = new THREE.Mesh(fromGeometryData(item.shell), pencilMaterial({ vertexColors: true, side: THREE.DoubleSide }));
      shell.userData = { building: building.id, floor: index + 1 }; shell.castShadow = shell.receiveShadow = true;
      const edges = new THREE.LineSegments(fromGeometryData(item.edges), new THREE.LineBasicMaterial({ color: '#383d39', transparent: true, opacity: .43, depthWrite: false }));
      edges.userData.pencilEdge = true; shell.add(edges); level.add(shell); level.userData.shell = shell;
    }
    model.add(level); return level;
  });
  finishStoreys(model, sources, storeys, model.userData.profile.height);
  return model;
}
