<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import campus from '../../../assets/maps/campus.json';
import { center, contains, constrainToBoundary } from './geometry.mjs';
import { venues, demoLocation } from './demo.js';
import { initialView } from './view.mjs';

const props = defineProps({ selected: String, floor: Number, activities: Array });
const emit = defineEmits(['select', 'floor', 'ready']);
const host = ref(null), failed = ref(false), loading = ref(true), labels = ref([]);
const panTarget = ref(initialView.target.filter((_, i) => i !== 1).join(','));
const activeVenue = computed(() => venues.find(v => v.id === props.selected));
let renderer, scene, camera, controls, observer, frame, buildings = [], exploded, floorMeshes = [], tween, pointerStart, disposed = false, explosionStart = 0, locationMarker, locationRing, contextBuildings;
const meshes = new Map(), selectable = [], raycaster = new THREE.Raycaster();
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const initialTarget = new THREE.Vector3(...initialView.target);
const initialCamera = initialTarget.clone().add(new THREE.Vector3(...initialView.offset));
function shape(points) { return new THREE.Shape(points.map(p => new THREE.Vector2(p[0], -p[1]))); }
function extrusion(points, depth) {
  const g = new THREE.ExtrudeGeometry(shape(points), { depth, bevelEnabled: false, steps: 1, curveSegments: 1 });
  g.rotateX(-Math.PI / 2);
  return g;
}
function surface(points, color, y) {
  const g = new THREE.ShapeGeometry(shape(points)); g.rotateX(-Math.PI / 2);
  const m = new THREE.Mesh(g, new THREE.MeshLambertMaterial({ color, side: THREE.DoubleSide })); m.position.y = y; scene.add(m);
}
function edge(mesh, color = 0x939ba1) {
  const line = new THREE.LineSegments(new THREE.EdgesGeometry(mesh.geometry, 28), new THREE.LineBasicMaterial({ color, transparent: true, opacity: .48 }));
  mesh.add(line);
}
function fly(position, target) {
  tween = { start: performance.now(), from: camera.position.clone(), to: position, targetFrom: controls.target.clone(), targetTo: target, duration: reducedMotion ? 0 : 1050 };
}
function disposeGroup(group) {
  group.traverse(o => { o.geometry?.dispose(); if (o.material) (Array.isArray(o.material) ? o.material : [o.material]).forEach(m => m.dispose()); });
  group.removeFromParent();
}
function expand() {
  if (!scene) return;
  if (exploded) { disposeGroup(exploded); exploded = null; }
  floorMeshes = [];
  // 聚焦时隔离主建筑，保留校区地形和道路作空间参照。
  for (const mesh of meshes.values()) mesh.visible = !props.selected;
  if (contextBuildings) contextBuildings.visible = !props.selected;
  if (locationMarker) locationMarker.visible = locationRing.visible = !props.selected;
  const building = buildings.find(b => b.id === props.selected);
  if (!building) { fly(initialCamera.clone(), initialTarget.clone()); return; }
  meshes.get(building.id).visible = false;
  exploded = new THREE.Group(); scene.add(exploded);
  const venue = activeVenue.value, count = venue?.floors || Math.min(6, building.levels || 3);
  const [cx, cz] = center(building.points), xs = building.points.map(p => p[0]), zs = building.points.map(p => p[1]);
  const minX = Math.min(...xs), maxX = Math.max(...xs), minZ = Math.min(...zs), maxZ = Math.max(...zs);
  const width = maxX - minX, length = maxZ - minZ, extent = Math.max(width, length, 45);
  const gap = Math.max(16, extent * .42);
  // 楼板沿真实 OSM 轮廓挤出；室内分隔只表达展示关系，不代表实际平面图。
  const cells = [];
  const cell = Math.max(9, Math.min(width, length) / 4);
  for (let x = minX + cell * .7; x < maxX - cell * .4; x += cell * 1.15) {
    for (let z = minZ + cell * .7; z < maxZ - cell * .4; z += cell * 1.15) {
      if ([[-.42, -.42], [.42, -.42], [.42, .42], [-.42, .42]].every(([dx, dz]) => contains([x + cell * dx, z + cell * dz], building.points))) cells.push([x, z]);
    }
  }
  if (!cells.length) cells.push([cx, cz]);
  for (let f = 1; f <= count; f++) {
    const level = new THREE.Group(); level.position.y = (f - 1) * gap; level.userData.finalY = level.position.y;
    const slab = new THREE.Mesh(extrusion(building.points, 1.1), new THREE.MeshLambertMaterial({ color: 0xfafaf7 }));
    slab.userData = { building: building.id, floor: f }; edge(slab); level.add(slab);
    const floorEvents = props.activities.filter(a => a.building === building.id && a.floor === f);
    cells.forEach(([x, z], i) => {
      const room = new THREE.Mesh(new THREE.BoxGeometry(cell * .78, .3, cell * .78), new THREE.MeshLambertMaterial({ color: i < floorEvents.length ? 0x86b9df : 0xe4e5e2 }));
      room.position.set(x, 1.4, z); room.userData = { building: building.id, floor: f, roomIndex: i }; edge(room, 0x9ca7ae); level.add(room);
      [[0, -.39, cell * .78, .65], [-.39, 0, .65, cell * .78], [.39, 0, .65, cell * .78]].forEach(([dx, dz, w, d]) => {
        const wall = new THREE.Mesh(new THREE.BoxGeometry(w, 3.2, d), new THREE.MeshLambertMaterial({ color: 0xf2f2ee }));
        wall.position.set(x + cell * dx, 3, z + cell * dz); wall.userData = { building: building.id, floor: f }; level.add(wall);
      });
    });
    exploded.add(level);
    floorMeshes.push({ level, slab, floor: f, point: new THREE.Vector3(maxX + 8, (f - 1) * gap + 2, cz), events: floorEvents });
  }
  const roof = new THREE.Mesh(extrusion(building.points, 1.3), new THREE.MeshLambertMaterial({ color: 0xd7dad8 }));
  roof.position.y = count * gap; roof.userData = { building: building.id, finalY: roof.position.y }; edge(roof); exploded.add(roof);
  const height = count * gap, target = new THREE.Vector3(cx, height * .48, cz);
  const radius = Math.hypot(width, height, length) / 2;
  const fitAngle = Math.min(camera.fov * Math.PI / 360, Math.atan(Math.tan(camera.fov * Math.PI / 360) * camera.aspect));
  const distance = radius / Math.sin(fitAngle);
  fly(target.clone().add(new THREE.Vector3(.7, .55, 1.2).normalize().multiplyScalar(distance)), target);
  explosionStart = performance.now();
  highlight();
}
function highlight() {
  for (const item of floorMeshes) {
    item.slab.material.color.set(item.floor === props.floor ? 0xc1dcf4 : 0xfafaf7);
    item.slab.children[0].material.color.set(item.floor === props.floor ? 0x3a87c0 : 0x939ba1);
    item.slab.children[0].material.opacity = item.floor === props.floor ? .95 : .48;
  }
}
function hit(event) {
  if (!pointerStart || Math.hypot(event.clientX - pointerStart.x, event.clientY - pointerStart.y) > 7 || performance.now() - pointerStart.time > 650) return;
  const rect = renderer.domElement.getBoundingClientRect();
  raycaster.setFromCamera(new THREE.Vector2((event.clientX - rect.left) / rect.width * 2 - 1, -(event.clientY - rect.top) / rect.height * 2 + 1), camera);
  const objects = exploded ? [...selectable.filter(m => m.visible), exploded] : selectable;
  const intersection = raycaster.intersectObjects(objects, true).find(item => item.object.isMesh && item.object.userData.building);
  if (!intersection) return;
  const data = intersection.object.userData;
  if (data.building === props.selected && data.floor) emit('floor', data.floor);
  else emit('select', data.building === props.selected ? null : data.building);
}
function coordinate(point) {
  const p = point.clone().project(camera), rect = host.value.getBoundingClientRect();
  return { x: (p.x + 1) * rect.width / 2, y: (1 - p.y) * rect.height / 2, visible: p.z > -1 && p.z < 1 && Math.abs(p.x) < .97 && Math.abs(p.y) < .95 };
}
function tick(now) {
  if (disposed) return;
  frame = requestAnimationFrame(tick);
  if (tween) {
    const t = tween.duration ? Math.min(1, (now - tween.start) / tween.duration) : 1, ease = 1 - (1 - t) ** 3;
    camera.position.lerpVectors(tween.from, tween.to, ease); controls.target.lerpVectors(tween.targetFrom, tween.targetTo, ease);
    if (t === 1) tween = null;
  }
  controls.update();
  // 在 OrbitControls 应用拖动及惯性后约束目标；相机同步平移，避免到校界时视角歪斜。
  const [x, z] = constrainToBoundary([controls.target.x, controls.target.z], campus.boundary);
  camera.position.x += x - controls.target.x; camera.position.z += z - controls.target.z;
  controls.target.x = x; controls.target.z = z;
  panTarget.value = `${x.toFixed(2)},${z.toFixed(2)}`;
  renderer.render(scene, camera);
  if (exploded) {
    const t = reducedMotion ? 1 : Math.min(1, (now - explosionStart) / 1000), ease = 1 - (1 - t) ** 3;
    exploded.children.forEach(o => { if (o.userData.finalY !== undefined) o.position.y = o.userData.finalY * (.12 + .88 * ease); });
  }
  // DOM 标签跟随 3D 相机投影，键盘也能点击；不依赖纹理字体或外网资源。
  labels.value = props.selected ? floorMeshes.map(f => ({ id: String(f.floor), floor: f.floor, title: `${f.floor}F${f.events.length ? ` · ${f.events[0].room}` : ''}`, count: f.events.length, ...coordinate(f.point) })) : venues.map(v => {
    const b = buildings.find(b => b.id === v.id), c = center(b.points);
    return { id: v.id, title: v.label, count: props.activities.filter(a => a.building === v.id).length, ...coordinate(new THREE.Vector3(c[0], b.height + 5, c[1])) };
  });
}
function zoom(scale) { if (!camera) return; tween = null; camera.position.sub(controls.target).multiplyScalar(scale).add(controls.target); }
function reset() { if (!scene) return; if (props.selected) emit('select', null); else fly(initialCamera.clone(), initialTarget.clone()); }
function locate() { if (!scene) return; fly(initialCamera.clone(), initialTarget.clone()); }
defineExpose({ zoom, reset, locate });
watch(() => props.selected, expand);
watch(() => props.floor, highlight);
watch(() => props.activities, () => {
  for (const item of floorMeshes) {
    item.events = props.activities.filter(a => a.building === props.selected && a.floor === item.floor);
    for (const room of item.level.children) if (room.userData.roomIndex !== undefined) room.material.color.set(room.userData.roomIndex < item.events.length ? 0x86b9df : 0xe4e5e2);
  }
});
onMounted(() => {
  try {
    scene = new THREE.Scene(); scene.background = new THREE.Color(0xf5f4ed); scene.fog = new THREE.Fog(0xf5f4ed, 1600, 3600);
    camera = new THREE.PerspectiveCamera(42, 1, 1, 7000); camera.position.copy(initialCamera);
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false }); renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setClearColor(0xf5f4ed); renderer.outputColorSpace = THREE.SRGBColorSpace; renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 1;
    renderer.domElement.setAttribute('aria-label', '燕园三维地图，拖动旋转，双指缩放。建筑也可通过下方列表选择。');
    host.value.prepend(renderer.domElement);
    controls = new OrbitControls(camera, renderer.domElement); controls.target.copy(initialTarget); controls.enableDamping = true;
    controls.minDistance = 65; controls.maxDistance = 2350; controls.minPolarAngle = .25; controls.maxPolarAngle = Math.PI * .46; controls.enablePan = true;
    controls.screenSpacePanning = false;
    controls.addEventListener('start', () => { tween = null; });
    scene.add(new THREE.HemisphereLight(0xffffff, 0xc7cdc7, 1.55));
    const sun = new THREE.DirectionalLight(0xfff9ec, 1.5); sun.position.set(-500, 900, 500); scene.add(sun);
    // 校界只用于交互范围；连续地面跨过校界，远处以同色雾自然淡出。
    surface([[-4000, -4000], [4000, -4000], [4000, 4000], [-4000, 4000]], 0xe6ede2, 0);
    [...campus.green, ...campus.context.green].forEach(g => surface(g.points, 0xd5e3cf, .07));
    [...campus.water, ...campus.context.water].forEach(w => surface(w.points, 0xb5d4df, .15));
    const roadVertices = [];
    for (const road of campus.context.roads) {
      const [a, b] = road.points, dx = b[0] - a[0], dz = b[1] - a[1], length = Math.hypot(dx, dz);
      if (!length) continue;
      const nx = -dz / length * road.width / 2, nz = dx / length * road.width / 2;
      const p = [[a[0] + nx, .23, a[1] + nz], [b[0] + nx, .23, b[1] + nz], [b[0] - nx, .23, b[1] - nz], [a[0] - nx, .23, a[1] - nz]];
      [0, 1, 2, 0, 2, 3].forEach(i => roadVertices.push(...p[i]));
    }
    const roads = new THREE.BufferGeometry(); roads.setAttribute('position', new THREE.Float32BufferAttribute(roadVertices, 3)); roads.computeVertexNormals();
    scene.add(new THREE.Mesh(roads, new THREE.MeshLambertMaterial({ color: 0xfaf9f3, side: THREE.DoubleSide })));
    buildings = campus.buildings;
    for (const b of buildings) {
      const mesh = new THREE.Mesh(extrusion(b.points, Math.min(80, Math.max(4, b.height))), new THREE.MeshLambertMaterial({ color: 0xe9e9e6 }));
      mesh.userData.building = b.id; edge(mesh); scene.add(mesh); meshes.set(b.id, mesh); selectable.push(mesh);
    }
    // 周边是实际轮廓的背景模型，合并绘制，避免增加数百次绘制调用。
    const contextGeometry = campus.context.buildings.map(b => extrusion(b.points, Math.min(80, Math.max(4, b.height))));
    if (contextGeometry.length) {
      contextBuildings = new THREE.Mesh(mergeGeometries(contextGeometry), new THREE.MeshLambertMaterial({ color: 0xe6e6e2 }));
      contextGeometry.forEach(g => g.dispose()); edge(contextBuildings); scene.add(contextBuildings);
    }
    locationMarker = new THREE.Mesh(new THREE.SphereGeometry(12, 12, 8), new THREE.MeshBasicMaterial({ color: 0x4387bb })); locationMarker.position.set(demoLocation[0], 12, demoLocation[1]); scene.add(locationMarker);
    locationRing = new THREE.Mesh(new THREE.RingGeometry(17, 24, 32), new THREE.MeshBasicMaterial({ color: 0x77a5c6, transparent: true, opacity: .5, side: THREE.DoubleSide })); locationRing.rotation.x = -Math.PI / 2; locationRing.position.set(demoLocation[0], .5, demoLocation[1]); scene.add(locationRing);
    observer = new ResizeObserver(() => { const { width, height } = host.value.getBoundingClientRect(); renderer.setSize(width, height); camera.aspect = width / height; camera.updateProjectionMatrix(); }); observer.observe(host.value);
    renderer.domElement.addEventListener('pointerdown', e => { pointerStart = { x: e.clientX, y: e.clientY, time: performance.now() }; });
    renderer.domElement.addEventListener('pointerup', hit);
    if (props.selected) expand();
    loading.value = false; emit('ready'); tick(performance.now());
  } catch (error) { console.error('校园 3D 地图初始化失败', error); failed.value = true; loading.value = false; }
});
onBeforeUnmount(() => { disposed = true; cancelAnimationFrame(frame); observer?.disconnect(); controls?.dispose(); if (scene) disposeGroup(scene); renderer?.dispose(); });
</script>

<template>
  <div ref="host" class="campus-scene" :data-building="selected || 'overview'" :data-floor="floor" :data-pan-target="panTarget">
    <div v-if="loading" class="scene-message" role="status">正在展开燕园…</div>
    <div v-if="failed" class="scene-message" role="alert">此设备暂不能绘制 3D 地图。<br>仍可用下方建筑列表查看楼层活动。</div>
    <template v-if="!failed">
      <div v-for="label in labels" v-show="label.visible && (selected || label.count)" :key="label.id" class="label-anchor" :style="{ left: `${label.x}px`, top: `${label.y}px` }">
        <button v-sketch v-memo="[label.id, label.title, label.count, selected, floor]" class="scene-label sketch" :class="{ 'floor-label': selected, current: selected && label.floor === floor }" :data-pencil="selected ? (label.floor === floor ? 'blue' : undefined) : 'yellow'" :aria-label="selected ? `查看 ${label.floor} 楼` : `展开${venues.find(v => v.id === label.id)?.short}`" :aria-pressed="selected ? label.floor === floor : undefined" @click="selected ? emit('floor', label.floor) : emit('select', label.id)">
          <span>{{ label.title }}</span><small v-if="label.count && !selected">{{ label.count }}</small>
        </button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.campus-scene { position: absolute; inset: 0; overflow: hidden; }
.campus-scene :deep(canvas) { display: block; width: 100%; height: 100%; touch-action: none; }
.scene-message { position: absolute; inset: 0; display: grid; place-content: center; text-align: center; font-size: 13px; line-height: 1.8; }
.label-anchor { position: absolute; z-index: 2; transform: translate(-50%, -100%); }
.scene-label { display: flex; align-items: center; gap: 4px; padding: 5px 8px; min-height: 32px; background: transparent; font-size: 11px; white-space: nowrap; }
.scene-label::after { content: ''; position: absolute; left: calc(50% - 3px); bottom: -4px; width: 4px; height: 4px; background: #ffdf32; border-right: 1px solid #53616b; border-bottom: 1px solid #53616b; transform: rotate(45deg); }
.scene-label small { background: #ffffff80; border-radius: 50%; padding: 1px 4px; font-size: 10px; }
.floor-label { background: transparent; padding: 5px 8px; min-height: 34px; font-size: 10px; }
.floor-label::after { background: #fbfaf4; }.floor-label.current::after { background: #b9d8f2; }
</style>
