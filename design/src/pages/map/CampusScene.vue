<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue';
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import campus from '../../../assets/maps/campus.json';
import { center, constrainToBoundary } from './geometry.mjs';
import { venues, demoLocation } from './demo.js';
import { initialView } from './view.mjs';
import { mapPalette } from './map-palette.mjs';
import { createBuilding, profileFor, footprintShape, extrudeFootprint } from './architecture.mjs';
import { createVegetation, createWater } from './landscape.mjs';
import { insideFootprint } from './rings.mjs';
import { pencilMaterial, pencilEdge } from './pencil-material.mjs';
import { prepareStoreys, transitionModel, animateModel } from './storeys.mjs';

const props = defineProps({ selected: String, floor: Number, activities: Array });
const emit = defineEmits(['select', 'floor', 'ready']);
const host = ref(null), failed = ref(false), loading = ref(true), labels = ref([]);
const modelIdentity = ref(''), modelProgress = ref('0');
const panTarget = ref(initialView.target.filter((_, i) => i !== 1).join(','));
let renderer, scene, camera, controls, observer, frame, buildings = [], focusedModel, floorMeshes = [], tween, pointerStart, disposed = false, locationMarker, locationRing, contextBuildings, vegetation;
const meshes = new Map(), selectable = [], raycaster = new THREE.Raycaster();
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const initialTarget = new THREE.Vector3(...initialView.target);
const initialCamera = initialTarget.clone().add(new THREE.Vector3(...initialView.offset));
function shape(points) { return footprintShape(points); }
function surface(points, color, y) {
  const g = new THREE.ShapeGeometry(shape(points)); g.rotateX(-Math.PI / 2);
  const m = new THREE.Mesh(g, pencilMaterial({ color, side: THREE.DoubleSide, scale: .3 })); m.position.y = y; m.receiveShadow = true; scene.add(m);
}
function fly(position, target) {
  tween = { start: performance.now(), from: camera.position.clone(), to: position, targetFrom: controls.target.clone(), targetTo: target, duration: reducedMotion ? 0 : 1050 };
}
function disposeGroup(group) {
  group.traverse(o => { o.geometry?.dispose(); if (o.material) (Array.isArray(o.material) ? o.material : [o.material]).forEach(m => { m.map?.dispose(); m.dispose(); }); });
  group.removeFromParent();
}
function cacheInterior(model, building) {
  const profile = model.userData.profile, levels = model.userData.storeys;
  if (model.userData.floorItems) return;
  const [cx, cz] = center(building.points), xs = building.points.map(p => p[0]), zs = building.points.map(p => p[1]);
  const minX = Math.min(...xs), maxX = Math.max(...xs), minZ = Math.min(...zs), maxZ = Math.max(...zs);
  const width = maxX - minX, length = maxZ - minZ, gap = Math.max(16, Math.max(width, length, 45) * .42);
  const cell = Math.max(9, Math.min(width, length) / 4), cells = [];
  for (let x = minX + cell * .7; x < maxX - cell * .4; x += cell * 1.15)
    for (let z = minZ + cell * .7; z < maxZ - cell * .4; z += cell * 1.15)
      if ([[-.42, -.42], [.42, -.42], [.42, .42], [-.42, .42]].every(([dx, dz]) => insideFootprint([x + cell * dx, z + cell * dz], building))) cells.push([x, z]);
  if (!cells.length && insideFootprint([cx, cz], building)) cells.push([cx, cz]);
  const items = [];
  for (const level of levels) {
    const f = level.userData.floor, interior = new THREE.Group(); interior.visible = false; level.add(interior);
    level.userData.interior = interior; level.userData.lift = (f - 1) * gap;
    const slab = new THREE.Mesh(extrudeFootprint(building, .35), pencilMaterial({ color: '#f4ecd8', transparent: true }));
    slab.position.y = .05; slab.receiveShadow = true; slab.userData = { building: building.id, floor: f };
    pencilEdge(slab, { opacity: .48 }); interior.add(slab);
    const pitch = profile.height / levels.length, wallHeight = Math.min(2, pitch * .42);
    cells.forEach(([x, z], i) => {
      const room = new THREE.Mesh(new THREE.BoxGeometry(cell * .78, .16, cell * .78), pencilMaterial({ color: '#e0deca', transparent: true }));
      room.position.set(x, .55, z); room.userData = { building: building.id, floor: f, roomIndex: i }; pencilEdge(room, { opacity: .35 }); interior.add(room);
      [[0, -.39, cell * .78, .4], [-.39, 0, .4, cell * .78], [.39, 0, .4, cell * .78]].forEach(([dx, dz, w, d]) => {
        const wall = new THREE.Mesh(new THREE.BoxGeometry(w, wallHeight, d), pencilMaterial({ color: '#e9debc', transparent: true }));
        wall.position.set(x + cell * dx, .65 + wallHeight / 2, z + cell * dz); wall.userData = { building: building.id, floor: f }; interior.add(wall);
      });
    });
    items.push({ level, slab, floor: f, x: maxX + 8, z: cz, events: [] });
  }
  const roof = model.userData.parts.find(p => p.userData.role === 'roof');
  if (roof) roof.userData.lift = levels.length * gap;
  model.userData.floorItems = items;
  model.userData.focusHeight = profile.height + levels.length * gap + (profile.roofRise || 6);
  model.userData.focusRadius = Math.hypot(width, model.userData.focusHeight, length) / 2;
}
function expand() {
  if (!scene || loading.value) return;
  const now = performance.now();
  // 从当前坐标反向收拢；不移除原模型，也不新建屋顶或楼体。
  if (focusedModel && focusedModel.userData.storeys) transitionModel(focusedModel, 0, now, reducedMotion ? 0 : 1050);
  const building = buildings.find(b => b.id === props.selected);
  focusedModel = building ? meshes.get(building.id) : null;
  floorMeshes = []; modelIdentity.value = focusedModel?.uuid || '';
  const scenic = focusedModel?.userData.profile.scenic;
  for (const model of meshes.values()) model.visible = !building || scenic || model === focusedModel || !!model.userData.transition;
  contextBuildings.visible = vegetation.visible = !building || !!scenic;
  locationMarker.visible = locationRing.visible = !building;
  renderer.shadowMap.needsUpdate = true;
  // 收起只合拢模型；终止尚未完成的聚焦，保留当前相机与观察目标。
  // 返回示例位置由显式 locate() 操作负责。
  if (!building) { tween = null; return; }
  const [cx, cz] = center(building.points);
  if (scenic) {
    const target = new THREE.Vector3(cx, 16, cz);
    fly(target.clone().add(new THREE.Vector3(68, 58, 100)), target); return;
  }
  cacheInterior(focusedModel, building);
  floorMeshes = focusedModel.userData.floorItems;
  updateActivities(); highlight();
  transitionModel(focusedModel, 1, now, reducedMotion ? 0 : 1050);
  const target = new THREE.Vector3(cx, focusedModel.userData.focusHeight * .48, cz);
  const fitAngle = Math.min(camera.fov * Math.PI / 360, Math.atan(Math.tan(camera.fov * Math.PI / 360) * camera.aspect));
  const distance = focusedModel.userData.focusRadius / Math.sin(fitAngle);
  fly(target.clone().add(new THREE.Vector3(.7, .55, 1.2).normalize().multiplyScalar(distance)), target);
}
function highlight() {
  for (const item of floorMeshes) {
    item.slab.material.color.set(item.floor === props.floor ? '#a9cfe5' : '#f4ecd8');
    item.slab.children[0].material.color.set(item.floor === props.floor ? '#425d70' : '#383d39');
  }
}
function updateActivities() {
  for (const item of floorMeshes) {
    item.events = props.activities.filter(a => a.building === props.selected && a.floor === item.floor);
    for (const room of item.level.userData.interior.children) if (room.userData.roomIndex !== undefined)
      room.material.color.set(room.userData.roomIndex < item.events.length ? '#85bbd8' : '#e0deca');
  }
}
function hit(event) {
  if (!pointerStart || Math.hypot(event.clientX - pointerStart.x, event.clientY - pointerStart.y) > 7 || performance.now() - pointerStart.time > 650) return;
  const rect = renderer.domElement.getBoundingClientRect();
  raycaster.setFromCamera(new THREE.Vector2((event.clientX - rect.left) / rect.width * 2 - 1, -(event.clientY - rect.top) / rect.height * 2 + 1), camera);
  const objects = selectable.filter(m => m.visible);
  const visible = object => { for (let o = object; o; o = o.parent) if (!o.visible) return false; return true; };
  const intersection = raycaster.intersectObjects(objects, true).find(item => item.object.isMesh && item.object.userData.building && visible(item.object));
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
    const t = tween.duration ? Math.min(1, (now - tween.start) / tween.duration) : 1, ease = t * t * (3 - 2 * t);
    camera.position.lerpVectors(tween.from, tween.to, ease); controls.target.lerpVectors(tween.targetFrom, tween.targetTo, ease);
    if (t === 1) tween = null;
  }
  controls.update();
  // 在 OrbitControls 应用拖动及惯性后约束目标；相机同步平移，避免到校界时视角歪斜。
  const [x, z] = constrainToBoundary([controls.target.x, controls.target.z], campus.boundary);
  camera.position.x += x - controls.target.x; camera.position.z += z - controls.target.z;
  controls.target.x = x; controls.target.z = z;
  panTarget.value = `${x.toFixed(2)},${z.toFixed(2)}`;
  for (const model of meshes.values()) {
    if (animateModel(model, now)) renderer.shadowMap.needsUpdate = true;
    if (props.selected && !focusedModel?.userData.profile.scenic && model !== focusedModel && !model.userData.transition) model.visible = false;
  }
  modelProgress.value = (focusedModel?.userData.progress || 0).toFixed(3);
  renderer.render(scene, camera);
  // DOM 标签跟随 3D 相机投影，键盘也能点击；不依赖纹理字体或外网资源。
  labels.value = props.selected ? floorMeshes.map(f => ({ id: String(f.floor), floor: f.floor, title: `${f.floor}F${f.events.length ? ` · ${f.events[0].room}` : ''}`, count: f.events.length, ...coordinate(new THREE.Vector3(f.x, f.level.position.y + 2, f.z)) })) : venues.map(v => {
    const b = buildings.find(b => b.id === v.id), c = center(b.points);
    return { id: v.id, title: v.label, count: props.activities.filter(a => a.building === v.id).length, ...coordinate(new THREE.Vector3(c[0], profileFor(b).height + 7, c[1])) };
  });
}
function zoom(scale) { if (!camera) return; tween = null; camera.position.sub(controls.target).multiplyScalar(scale).add(controls.target); }
function locate() { if (!scene) return; fly(initialCamera.clone(), initialTarget.clone()); }
defineExpose({ zoom, locate });
watch(() => props.selected, expand);
watch(() => props.floor, highlight);
watch(() => props.activities, updateActivities);
onMounted(async () => {
  try {
    scene = new THREE.Scene(); scene.background = new THREE.Color(mapPalette.sky); scene.fog = new THREE.Fog(mapPalette.sky, 650, 2000);
    camera = new THREE.PerspectiveCamera(42, 1, 1, 7000); camera.position.copy(initialCamera);
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false }); renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setClearColor(mapPalette.sky); renderer.outputColorSpace = THREE.SRGBColorSpace; renderer.toneMapping = THREE.NoToneMapping;
    renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFShadowMap; renderer.shadowMap.autoUpdate = false;
    renderer.domElement.setAttribute('aria-label', '燕园三维地图，拖动旋转，双指缩放。建筑也可通过下方列表选择。');
    host.value.prepend(renderer.domElement);
    controls = new OrbitControls(camera, renderer.domElement); controls.target.copy(initialTarget); controls.enableDamping = true;
    controls.minDistance = 65; controls.maxDistance = 2350; controls.minPolarAngle = .25; controls.maxPolarAngle = Math.PI * .46; controls.enablePan = true;
    controls.screenSpacePanning = false;
    controls.addEventListener('start', () => { tween = null; });
    scene.add(new THREE.HemisphereLight(0xfffdf4, 0xeee8c7, 1.05));
    const sun = new THREE.DirectionalLight(0xffffff, .65); sun.position.set(-450, 800, 450); sun.castShadow = true;
    sun.shadow.mapSize.set(2048, 2048); Object.assign(sun.shadow.camera, { left: -1250, right: 1250, top: 1250, bottom: -1250, near: 10, far: 2400 }); sun.shadow.bias = -.0002; sun.shadow.normalBias = .5; scene.add(sun);
    // 校界只用于交互范围；连续地面跨过校界，远处以同色雾自然淡出。
    surface([[-4000, -4000], [4000, -4000], [4000, 4000], [-4000, 4000]], mapPalette.ground, 0);
    [...campus.green, ...campus.context.green].forEach(g => surface(g.points, g.kind === 'pitch' ? mapPalette.pitch : mapPalette.green, .07));
    [...campus.water, ...campus.context.water].forEach(w => scene.add(createWater(w)));
    const roadVertices = [];
    for (const road of campus.context.roads) {
      const [a, b] = road.points, dx = b[0] - a[0], dz = b[1] - a[1], length = Math.hypot(dx, dz);
      if (!length) continue;
      const nx = -dz / length * road.width / 2, nz = dx / length * road.width / 2;
      const p = [[a[0] + nx, .23, a[1] + nz], [b[0] + nx, .23, b[1] + nz], [b[0] - nx, .23, b[1] - nz], [a[0] - nx, .23, a[1] - nz]];
      [0, 1, 2, 0, 2, 3].forEach(i => roadVertices.push(...p[i]));
    }
    const roads = new THREE.BufferGeometry(); roads.setAttribute('position', new THREE.Float32BufferAttribute(roadVertices, 3)); roads.computeVertexNormals();
    const roadMesh = new THREE.Mesh(roads, pencilMaterial({ color: mapPalette.road, side: THREE.DoubleSide, scale: .5 })); roadMesh.receiveShadow = true; scene.add(roadMesh);
    buildings = campus.buildings;
    let preparedCount = 0;
    for (const b of buildings) {
      const mesh = prepareStoreys(createBuilding(b), b, venues.find(v => v.id === b.id)?.floors || Math.min(6, profileFor(b).floors)); scene.add(mesh); meshes.set(b.id, mesh); selectable.push(mesh);
      if (++preparedCount % 16 === 0) {
        await new Promise(resolve => setTimeout(resolve, 0));
        if (disposed) return;
      }
    }
    // 四栋活动入口提前缓存室内，首点也无需临时创建这一批几何。
    for (const venue of venues) cacheInterior(meshes.get(venue.id), buildings.find(b => b.id === venue.id));
    // 周边是实际轮廓的背景模型，合并绘制，避免增加数百次绘制调用。
    const contextGeometry = campus.context.buildings.map(b => {
      const g = extrudeFootprint(b, profileFor(b).height), color = new THREE.Color(profileFor(b).wall), colors = [];
      for (let i = 0; i < g.attributes.position.count; i++) colors.push(color.r, color.g, color.b);
      g.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3)); return g;
    });
    if (contextGeometry.length) {
      contextBuildings = new THREE.Mesh(mergeGeometries(contextGeometry), pencilMaterial({ vertexColors: true })); contextBuildings.castShadow = true; contextBuildings.receiveShadow = true;
      contextGeometry.forEach(g => g.dispose()); pencilEdge(contextBuildings, { opacity: .18, threshold: 42 }); scene.add(contextBuildings);
    }
    vegetation = createVegetation(campus); scene.add(vegetation); renderer.shadowMap.needsUpdate = true;
    locationMarker = new THREE.Mesh(new THREE.SphereGeometry(4.5, 16, 10), new THREE.MeshBasicMaterial({ color: 0x4387bb })); locationMarker.position.set(demoLocation[0], 4.5, demoLocation[1]); scene.add(locationMarker);
    locationRing = new THREE.Mesh(new THREE.RingGeometry(7, 10, 32), new THREE.MeshBasicMaterial({ color: 0x77a5c6, transparent: true, opacity: .5, side: THREE.DoubleSide })); locationRing.rotation.x = -Math.PI / 2; locationRing.position.set(demoLocation[0], .5, demoLocation[1]); scene.add(locationRing);
    observer = new ResizeObserver(() => { const { width, height } = host.value.getBoundingClientRect(); renderer.setSize(width, height); camera.aspect = width / height; camera.updateProjectionMatrix(); }); observer.observe(host.value);
    renderer.domElement.addEventListener('pointerdown', e => { pointerStart = { x: e.clientX, y: e.clientY, time: performance.now() }; });
    renderer.domElement.addEventListener('pointerup', hit);
    await renderer.compileAsync(scene, camera);
    if (disposed) return;
    loading.value = false;
    if (props.selected) expand();
    emit('ready'); tick(performance.now());
  } catch (error) { if (!disposed) { console.error('校园 3D 地图初始化失败', error); failed.value = true; loading.value = false; } }
});
onBeforeUnmount(() => { disposed = true; cancelAnimationFrame(frame); observer?.disconnect(); controls?.dispose(); if (scene) disposeGroup(scene); renderer?.dispose(); });
</script>

<template>
  <div ref="host" class="campus-scene" :data-building="selected || 'overview'" :data-floor="floor" :data-pan-target="panTarget" :data-model-id="modelIdentity" :data-model-progress="modelProgress">
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
