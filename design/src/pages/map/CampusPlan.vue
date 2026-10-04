<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import campus from '../../../assets/maps/campus.json';
import { demoLocation, venues } from './demo.js';
import { center, constrainToBoundary } from './geometry.mjs';
import { profileFor } from './model-profiles.mjs';
import { treeLayout } from './landscape.mjs';
import { mapPalette } from './map-palette.mjs';
import { createPlanPatterns, pencilPlanPath } from './plan-pencil.mjs';
import { initialPlanScale, planAnchor, worldToPlan, planToWorld, zoomPlan, panPlan, pinchPlan,
  planBounds, intersectsPlan, pickPlanBuilding, planScaleBar } from './plan-view.mjs';

const props = defineProps({ selected: String, focusPoint: Array, activities: Array,
  focusInset: { type: Number, default: 0 }, startingView: Object });
const emit = defineEmits(['select']);
const host = ref(null), canvas = ref(null), labels = ref([]), ready = ref(false);
const displayView = ref({ center: [...demoLocation], scale: .54 });
const scaleBar = computed(() => planScaleBar(displayView.value.scale));
const panTarget = computed(() => displayView.value.center.map(value => value.toFixed(1)).join(','));
let ctx, patterns, observer, frame, motion, reducedMotion, width = 0, height = 0, dpr = 1;
let view = { center: [...demoLocation], scale: .54 }, surfaces = [], buildings = [], roads = [], trees = [];
let gesture, velocity = [0, 0], lastMoveTime = 0;
const pointers = new Map();
const anchor = () => planAnchor(width, height, props.focusInset);
const pointInView = event => { const rect = canvas.value.getBoundingClientRect(); return [event.clientX - rect.left, event.clientY - rect.top]; };
function schedule() { if (!frame) frame = requestAnimationFrame(draw); }
function stop() { motion = null; velocity = [0, 0]; }
function fly(target) {
  stop(); target.center = constrainToBoundary(target.center, campus.boundary);
  if (reducedMotion.matches) view = target;
  else motion = { from: { center: [...view.center], scale: view.scale }, target, start: performance.now(), duration: 720 };
  schedule();
}
function focusBuilding() {
  const building = campus.buildings.find(item => item.id === props.selected);
  if (!building) { stop(); schedule(); return; }
  const box = planBounds(building.points);
  const available = Math.max(130, height - props.focusInset - 150);
  const scale = Math.max(initialPlanScale(width), Math.min(1.6, width * .6 / Math.max(30, box.right - box.left), available * .55 / Math.max(30, box.bottom - box.top)));
  fly({ center: center(building.points), scale });
}
function focusPlace() { if (props.focusPoint) fly({ center: [...props.focusPoint], scale: Math.max(view.scale, initialPlanScale(width)) }); }
function zoom(ratio, point = anchor()) {
  stop(); view = zoomPlan(view, view.scale / ratio, point, anchor(), campus.boundary); schedule();
}
function locate() { fly({ center: [...demoLocation], scale: initialPlanScale(width) }); }
defineExpose({ zoom, locate, getView: () => ({ center: [...view.center], scale: view.scale }) });

function surface(item, color, type) {
  return { ...item, color, type, path: pencilPlanPath(item.points, item.holes), bounds: planBounds(item.points) };
}
function prepare() {
  patterns = createPlanPatterns(ctx, [...Object.values(mapPalette).flat(), '#efeddd', '#99cbd7']);
  surfaces = [
    ...[...campus.context.green, ...campus.green].map(item => surface(item, item.kind === 'pitch' ? mapPalette.pitch : mapPalette.green, 'green')),
    ...[...campus.context.water, ...campus.water].map(item => surface(item, mapPalette.water, 'water')),
  ];
  buildings = [...campus.context.buildings.map(item => surface(item, '#efeddd', 'context')),
    ...campus.buildings.map(item => ({ ...surface(item, profileFor(item).roof, 'building'), profile: profileFor(item) }))];
  roads = campus.context.roads.map(item => ({ ...item, bounds: planBounds(item.points) }));
  trees = treeLayout(campus).map(item => {
    const path = new Path2D(), [x, y] = item.point;
    // 圆润、略有起伏的树冠，保持与 3D 地图一致的位置和色阶。
    for (let i = 0; i <= 16; i++) {
      const angle = i / 16 * Math.PI * 2, radius = item.size * (1 + .08 * Math.sin(angle * 5 + item.shade * 6));
      const point = [x + Math.cos(angle) * radius, y + Math.sin(angle) * radius];
      if (!i) path.moveTo(...point); else path.lineTo(...point);
    }
    path.closePath();
    return { ...item, path, color: mapPalette.trees[Math.floor(item.shade * mapPalette.trees.length)] };
  });
}
function paintSurface(item, visible) {
  if (!intersectsPlan(item.bounds, visible)) return;
  ctx.fillStyle = patterns[item.color]; ctx.fill(item.path, 'evenodd');
  if (item.type === 'water') {
    ctx.strokeStyle = '#6c7d64'; ctx.lineWidth = .8 / view.scale; ctx.globalAlpha = .6; ctx.stroke(item.path); ctx.globalAlpha = 1;
    ctx.save(); ctx.clip(item.path, 'evenodd'); ctx.strokeStyle = '#fffaf0'; ctx.lineWidth = .7 / view.scale; ctx.globalAlpha = .6;
    const { left, right, top, bottom } = item.bounds;
    ctx.beginPath();
    for (let y = top + 12; y < bottom; y += 18) for (let x = left + 10; x < right; x += 35) {
      ctx.moveTo(x, y); ctx.quadraticCurveTo(x + 3, y - .9, x + 7, y);
    }
    ctx.stroke(); ctx.restore();
  } else if (item.kind === 'pitch' && view.scale > .4) {
    const { left, right, top, bottom } = item.bounds;
    ctx.save(); ctx.clip(item.path); ctx.strokeStyle = '#ffffff'; ctx.lineWidth = .9 / view.scale; ctx.globalAlpha = .7;
    ctx.strokeRect(left + 4, top + 4, right - left - 8, bottom - top - 8);
    ctx.beginPath(); ctx.moveTo((left + right) / 2, top + 4); ctx.lineTo((left + right) / 2, bottom - 4); ctx.stroke(); ctx.restore();
  }
}
function paintBuilding(item, visible) {
  if (!intersectsPlan(item.bounds, visible, 6)) return;
  ctx.save();
  ctx.translate(1.6, 2); ctx.globalAlpha = item.type === 'context' ? .09 : .16;
  ctx.fillStyle = '#687364'; ctx.fill(item.path, 'evenodd'); ctx.restore();
  ctx.fillStyle = patterns[item.color]; ctx.fill(item.path, 'evenodd');
  if (item.type === 'building') {
    ctx.save(); ctx.clip(item.path, 'evenodd');
    ctx.strokeStyle = patterns[mapPalette.walls[0]]; ctx.lineWidth = 4.2 / view.scale; ctx.stroke(item.path);
    const { left, right, top, bottom } = item.bounds, cx = (left + right) / 2, cy = (top + bottom) / 2;
    ctx.globalAlpha = .24; ctx.strokeStyle = '#383d39'; ctx.lineWidth = .65 / view.scale;
    ctx.beginPath();
    if (item.profile.style === 'pagoda') { ctx.arc(cx, cy, Math.min(right - left, bottom - top) * .27, 0, Math.PI * 2); }
    else if (['traditional', 'gate', 'hall', 'library'].includes(item.profile.style)) {
      if (right - left > bottom - top) { ctx.moveTo(left, cy); ctx.lineTo(right, cy); }
      else { ctx.moveTo(cx, top); ctx.lineTo(cx, bottom); }
      for (const point of [[left, top], [right, top], [left, bottom], [right, bottom]]) { ctx.moveTo(...point); ctx.lineTo(cx, cy); }
    } else if (view.scale > .75 && right - left > 25 && bottom - top > 25) {
      ctx.rect(cx - 5, cy - 4, 10, 8); ctx.rect(cx + 9, cy - 4, 6, 8);
    }
    ctx.stroke(); ctx.restore();
  }
  ctx.strokeStyle = '#383d39'; ctx.globalAlpha = item.type === 'context' ? .27 : .76;
  ctx.lineWidth = (item.type === 'context' ? .6 : 1.05) / view.scale; ctx.stroke(item.path); ctx.globalAlpha = 1;
  if (item.id === props.selected) {
    ctx.strokeStyle = '#408fd3'; ctx.lineWidth = 3 / view.scale; ctx.stroke(item.path);
  }
}
function updateLabels() {
  const counts = new Map();
  for (const item of props.activities || []) counts.set(item.building, (counts.get(item.building) || 0) + 1);
  const landmarkIds = ['r3249649', '240825562', '226704254', '445016209'];
  const candidates = campus.buildings.filter(item => item.name && (item.id === props.selected || counts.has(item.id) || landmarkIds.includes(item.id) || view.scale > 1.1))
    .map(item => ({ ...item, rank: item.id === props.selected ? 0 : counts.has(item.id) ? 1 : landmarkIds.includes(item.id) ? 2 : 3 }))
    .sort((a, b) => a.rank - b.rank || a.id.localeCompare(b.id));
  const occupied = [
    { left: width - 67, right: width, top: 100, bottom: 345 },
    { left: 8, right: 53, top: 132, bottom: 182 },
    { left: 10, right: 120, top: height - props.focusInset - 80, bottom: height - props.focusInset - 48 },
    { left: 10, right: width - 70, top: height - props.focusInset - 46, bottom: height - props.focusInset - 10 },
  ], next = [];
  for (const item of candidates) {
    const [x, y] = worldToPlan(center(item.points), view, anchor());
    const title = venues.find(venue => venue.id === item.id)?.short || item.name.replace('北京大学', '').split('（')[0];
    const count = counts.get(item.id) || 0, labelWidth = Math.min(134, title.length * 11 + 20 + (count ? 20 : 0));
    for (const offset of [12, -36]) {
      const box = { left: x - labelWidth / 2, right: x + labelWidth / 2, top: y + offset, bottom: y + offset + 30 };
      if (box.left < 8 || box.right > width - 8 || box.top < 102 || box.bottom > height - 22 || occupied.some(other => intersectsPlan(box, other, 5))) continue;
      occupied.push(box); next.push({ id: item.id, title, count, x, y: box.top - 7 }); break;
    }
    if (next.length >= (width < 360 ? 10 : 14)) break;
  }
  const lake = campus.water.find(item => item.name === '未名湖');
  if (lake) {
    const [x, y] = worldToPlan(center(lake.points), view, anchor());
    lakePlacement: for (const shift of [0, 20, -20]) for (const offset of [-20, 12, 34]) {
      const lx = x + shift, top = y + offset, box = { left: lx - 32, right: lx + 32, top, bottom: top + 28 };
      if (lx > 35 && lx < width - 35 && top > 92 && box.bottom < height - 28 && !occupied.some(other => intersectsPlan(box, other, 3))) {
        next.push({ id: 'lake', title: '未名湖', x: lx, y: top, scenic: true }); break lakePlacement;
      }
    }
  }
  labels.value = next;
}
function draw(time) {
  frame = null; if (!ctx || !width) return;
  if (motion) {
    const progress = Math.min(1, (time - motion.start) / motion.duration), ease = 1 - (1 - progress) ** 3;
    view = { center: motion.from.center.map((value, i) => value + (motion.target.center[i] - value) * ease), scale: motion.from.scale + (motion.target.scale - motion.from.scale) * ease };
    view.center = constrainToBoundary(view.center, campus.boundary);
    if (progress === 1) motion = null;
  }
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, width, height);
  const [ax, ay] = anchor(); ctx.translate(ax, ay); ctx.scale(view.scale, view.scale); ctx.translate(-view.center[0], -view.center[1]);
  const start = planToWorld([0, 0], view, anchor()), end = planToWorld([width, height], view, anchor());
  const visible = { left: start[0], top: start[1], right: end[0], bottom: end[1] };
  ctx.fillStyle = patterns[mapPalette.ground]; ctx.fillRect(visible.left, visible.top, visible.right - visible.left, visible.bottom - visible.top);
  ctx.lineCap = ctx.lineJoin = 'round';
  surfaces.forEach(item => paintSurface(item, visible));
  ctx.strokeStyle = patterns[mapPalette.road];
  for (const road of roads) {
    if (!intersectsPlan(road.bounds, visible, road.width)) continue;
    ctx.lineWidth = road.width; ctx.beginPath(); ctx.moveTo(...road.points[0]);
    road.points.slice(1).forEach(point => ctx.lineTo(...point)); ctx.stroke();
  }
  buildings.forEach(item => paintBuilding(item, visible));
  for (const tree of trees) {
    const [x, y] = tree.point;
    if (x < visible.left - 6 || x > visible.right + 6 || y < visible.top - 6 || y > visible.bottom + 6) continue;
    ctx.fillStyle = patterns[tree.color]; ctx.fill(tree.path);
    ctx.strokeStyle = '#526743'; ctx.globalAlpha = .38; ctx.lineWidth = .6 / view.scale; ctx.stroke(tree.path); ctx.globalAlpha = 1;
  }
  // 示例定位固定，与 3D 蓝点共用 demoLocation，不获取设备位置。
  ctx.beginPath(); ctx.arc(...demoLocation, 10 / view.scale, 0, Math.PI * 2); ctx.fillStyle = '#84bdf866'; ctx.fill();
  ctx.beginPath(); ctx.arc(...demoLocation, 4.5 / view.scale, 0, Math.PI * 2); ctx.fillStyle = '#428bd1'; ctx.fill(); ctx.strokeStyle = '#ffffff'; ctx.lineWidth = 1.8 / view.scale; ctx.stroke();
  displayView.value = { center: [...view.center], scale: view.scale }; updateLabels();
  if (motion) schedule();
}
function resize() {
  const first = !width; width = host.value.clientWidth; height = host.value.clientHeight;
  dpr = Math.min(window.devicePixelRatio || 1, 2); canvas.value.width = Math.round(width * dpr); canvas.value.height = Math.round(height * dpr);
  if (first) view = props.startingView ? { center: [...props.startingView.center], scale: props.startingView.scale } : { center: [...demoLocation], scale: initialPlanScale(width) };
  schedule();
}
function pointerDown(event) {
  if (event.button !== 0 && event.pointerType === 'mouse') return;
  stop(); const point = pointInView(event); pointers.set(event.pointerId, point); canvas.value.setPointerCapture(event.pointerId);
  gesture = { start: point, moved: pointers.size > 1 }; lastMoveTime = performance.now();
}
function pointerMove(event) {
  if (!pointers.has(event.pointerId) || !gesture) return;
  const before = [...pointers.values()]; pointers.set(event.pointerId, pointInView(event)); const after = [...pointers.values()];
  if (after.length === 1) {
    const delta = after[0].map((value, i) => value - before[0][i]), elapsed = Math.max(8, performance.now() - lastMoveTime);
    if (Math.hypot(...after[0].map((value, i) => value - gesture.start[i])) > 6) gesture.moved = true;
    view = panPlan(view, delta, campus.boundary); velocity = delta.map(value => value / elapsed);
  } else {
    gesture.moved = true; velocity = [0, 0];
    view = pinchPlan(view, before, after, anchor(), campus.boundary);
  }
  lastMoveTime = performance.now(); schedule();
}
function pointerUp(event) {
  if (!pointers.has(event.pointerId)) return;
  const point = pointers.get(event.pointerId); pointers.delete(event.pointerId);
  if (event.type !== 'pointercancel' && gesture && !gesture.moved && !pointers.size) {
    const id = pickPlanBuilding(planToWorld(point, view, anchor()), campus.buildings);
    if (id) emit('select', id === props.selected ? null : id);
  } else if (gesture?.moved && !pointers.size && performance.now() - lastMoveTime < 80 && !reducedMotion.matches && event.type !== 'pointercancel') {
    const drift = velocity.map(value => Math.max(-110, Math.min(110, value * 110)));
    fly(panPlan(view, drift, campus.boundary));
  }
  if (!pointers.size) gesture = null; else { gesture.moved = true; gesture.start = [...pointers.values()][0]; }
  velocity = [0, 0]; schedule();
}
function wheel(event) { zoom(Math.exp(Math.max(-150, Math.min(150, event.deltaY)) * .0035), pointInView(event)); }
function keyboard(event) {
  if (event.target !== host.value && event.target !== canvas.value) return;
  const delta = { ArrowLeft: [45, 0], ArrowRight: [-45, 0], ArrowUp: [0, 45], ArrowDown: [0, -45] }[event.key];
  if (delta) { event.preventDefault(); stop(); view = panPlan(view, delta, campus.boundary); schedule(); }
  else if (['+', '=', '-'].includes(event.key)) { event.preventDefault(); zoom(event.key === '-' ? 1.25 : .8); }
}
watch(() => props.selected, focusBuilding);
watch(() => props.focusPoint, focusPlace);
watch(() => props.activities, schedule);
watch(() => props.focusInset, schedule);
onMounted(() => {
  reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)'); ctx = canvas.value.getContext('2d');
  prepare(); resize(); observer = new ResizeObserver(resize); observer.observe(host.value); ready.value = true;
  if (props.selected) focusBuilding(); else if (props.focusPoint) focusPlace();
});
onBeforeUnmount(() => { cancelAnimationFrame(frame); observer?.disconnect(); pointers.clear(); patterns = null; });
</script>

<template>
  <div ref="host" class="campus-plan" tabindex="0" aria-label="燕园俯视地图，拖动平移，双指或滚轮缩放，也可使用方向键和加减键" :data-ready="ready" :data-building="selected || 'overview'" :data-pan-target="panTarget" :data-zoom="displayView.scale.toFixed(3)" @keydown="keyboard">
    <canvas ref="canvas" aria-label="北京大学燕园二维彩铅地图" role="img" @pointerdown="pointerDown" @pointermove="pointerMove" @pointerup="pointerUp" @pointercancel="pointerUp" @wheel.prevent="wheel"></canvas>
    <div class="plan-labels">
      <div v-for="label in labels" :key="label.id" class="plan-label-anchor" :style="{ left: `${label.x}px`, top: `${label.y}px` }">
        <span v-if="label.scenic" class="lake-label">{{ label.title }}</span>
        <button v-else v-memo="[label.id, label.title, label.count, selected === label.id]" class="plan-label" type="button" :aria-label="`查看${label.title}${label.count ? `，${label.count}场活动` : ''}`" :aria-pressed="selected === label.id" @click="emit('select', selected === label.id ? null : label.id)"><span v-sketch class="label-paper sketch sketch-white" :data-pencil="selected === label.id ? 'blue' : label.count ? 'yellow' : undefined">{{ label.title }}<small v-if="label.count">{{ label.count }}</small></span></button>
      </div>
    </div>
    <div class="plan-compass" aria-label="地图上方为北"><span>北</span><svg viewBox="0 0 26 32" aria-hidden="true"><path d="M13 3 Q9 15 5 27 L13 23 21 27 Q17 14 13 3Z" fill="#fffaf0" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round"/><path d="M13 3 13 23 5 27Z" fill="#6ba8d7" opacity=".8"/></svg></div>
    <div class="plan-scale" :style="{ bottom: `${focusInset + 53}px` }" aria-label="地图比例尺"><svg :width="scaleBar.pixels + 4" height="9" aria-hidden="true"><path :d="`M2 1 L2 6 Q${scaleBar.pixels / 2} 5.5 ${scaleBar.pixels + 2} 6 L${scaleBar.pixels + 2} 1`" /></svg><span>{{ scaleBar.meters }}米</span></div>
  </div>
</template>

<style scoped>
.campus-plan { position: absolute; inset: 0; overflow: hidden; background: #c2ef98; }.campus-plan:focus-visible { outline: 2px dashed #408fd3; outline-offset: -3px; }
canvas { display: block; width: 100%; height: 100%; touch-action: none; cursor: grab; }canvas:active { cursor: grabbing; }
.plan-labels { position: absolute; inset: 0; pointer-events: none; }.plan-label-anchor { position: absolute; transform: translateX(-50%); }.plan-label { display: flex; align-items: center; justify-content: center; min-height: 44px; padding: 6px 0; border: 0; background: transparent; pointer-events: auto; font: inherit; color: var(--ink); }
.label-paper { display: flex; align-items: center; justify-content: center; gap: 6px; max-width: 134px; padding: 5px 8px; font-size: 11px; white-space: nowrap; }.label-paper small { display: grid; place-items: center; min-width: 17px; height: 17px; padding: 0 3px; font-size: 10px; color: #2b577a; }.lake-label { display: block; padding: 7px 0; font-size: 15px; color: #326f85; letter-spacing: 3px; text-shadow: 0 1px #fffaf0aa; }
.plan-compass { position: absolute; left: 19px; top: 135px; display: flex; flex-direction: column; align-items: center; gap: 2px; color: #405f65; pointer-events: none; }.plan-compass span { font-size: 11px; }.plan-compass svg { width: 21px; height: 27px; }
.plan-scale { position: absolute; left: 20px; display: flex; flex-direction: column; align-items: flex-start; gap: 2px; pointer-events: none; color: #405550; text-shadow: 0 1px #ffffff; }.plan-scale svg { fill: none; stroke: currentColor; stroke-width: 1.5; stroke-linecap: round; stroke-linejoin: round; }.plan-scale span { font-size: 10px; }
@media(max-width:359px) { .label-paper { font-size: 10px; padding-inline: 6px; }.lake-label { font-size: 13px; } }
</style>
