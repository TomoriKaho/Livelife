<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { drawerStates, drawerHeights, draggedHeight, nextDrawerState, snapDrawerState } from './drawer-gesture.mjs';

const emit = defineEmits(['measure']);
const state = ref('middle'), dragging = ref(false), dragHeight = ref(0);
const heights = ref({ hidden: 38, middle: 180, expanded: 540 }), bottom = ref(86);
const root = ref(null), content = ref(null);
let gesture, observer, lastDragEnd = -Infinity;
const height = computed(() => dragging.value ? dragHeight.value : heights.value[state.value]);
const handleLabel = computed(() => state.value === 'hidden' ? '显示活动信息' : state.value === 'expanded' ? '收起活动信息' : '展开活动信息');

function setState(value) {
  if (!drawerStates.includes(value)) return;
  gesture = null; dragging.value = false; state.value = value;
  if (content.value) content.value.scrollTop = 0;
}
function collapse() { setState('middle'); }
defineExpose({ collapse, setState, getState: () => state.value });

function start(x, y, fromHandle) {
  gesture = { x, y, deltaX: 0, deltaY: 0, height: height.value, fromState: state.value,
    canDrag: fromHandle || state.value !== 'expanded' || content.value.scrollTop <= 1 };
}
function move(x, y, event) {
  if (!gesture?.canDrag) return;
  gesture.deltaX = x - gesture.x; gesture.deltaY = y - gesture.y;
  if (!dragging.value && (Math.abs(gesture.deltaY) < 8 || Math.abs(gesture.deltaY) <= Math.abs(gesture.deltaX) * 1.2)) return;
  // 展开时向上滑动交给正文滚动；从顶部下拉才收起。
  if (gesture.fromState === 'expanded' && gesture.deltaY < 0 && !dragging.value) return;
  if (event.cancelable) event.preventDefault();
  dragging.value = true;
  dragHeight.value = draggedHeight(gesture.height, gesture.deltaY, heights.value);
}
function finish(cancelled = false) {
  if (dragging.value && gesture) {
    state.value = cancelled ? gesture.fromState : snapDrawerState({ ...gesture, height: dragHeight.value, heights: heights.value });
    lastDragEnd = performance.now();
    if (state.value !== 'expanded') content.value.scrollTop = 0;
  }
  gesture = null; dragging.value = false;
}
function pointerStart(event) {
  if (!event.isPrimary || event.button !== 0) return;
  start(event.clientX, event.clientY, true);
  event.currentTarget.setPointerCapture(event.pointerId);
}
function touchStart(event) {
  if (event.touches.length !== 1) { finish(true); return; }
  start(event.touches[0].clientX, event.touches[0].clientY, false);
}
function touchMove(event) {
  if (event.touches.length !== 1) { finish(true); return; }
  move(event.touches[0].clientX, event.touches[0].clientY, event);
}
function stopDragClick(event) {
  if (performance.now() - lastDragEnd < 250) { event.preventDefault(); event.stopPropagation(); }
}
function step(direction) {
  state.value = nextDrawerState(state.value, direction);
  if (state.value !== 'expanded') content.value.scrollTop = 0;
}
function toggle() { step(state.value === 'expanded' ? -1 : 1); }
function chrome(shell) {
  return {
    nav: shell.querySelector('.bottom-nav'),
    header: shell.querySelector('.lab-header, .app-header'),
  };
}
function measure() {
  const shell = root.value?.closest('.phone-shell');
  const { nav, header } = shell ? chrome(shell) : {};
  if (!shell || !nav || !header) return;
  const navHeight = nav.getBoundingClientRect().height;
  bottom.value = navHeight;
  heights.value = drawerHeights(shell.getBoundingClientRect().height, header.getBoundingClientRect().height, navHeight);
  emit('measure', heights.value.middle);
}
onMounted(() => {
  measure(); observer = new ResizeObserver(measure);
  const shell = root.value.closest('.phone-shell');
  [shell, ...Object.values(chrome(shell))].filter(Boolean).forEach(element => observer.observe(element));
});
onBeforeUnmount(() => observer?.disconnect());
</script>

<template>
  <Teleport to=".phone-shell" defer>
    <aside ref="root" class="activity-drawer" :class="{ dragging }" aria-label="首页活动信息"
      :data-state="state" :style="{ height: `${height}px`, bottom: `${bottom}px` }" @click.capture="stopDragClick">
      <svg class="drawer-edge" viewBox="0 0 430 3" preserveAspectRatio="none" aria-hidden="true"><path d="M0 1.5 H430" /></svg>
      <button class="drawer-handle" type="button" :aria-expanded="state !== 'hidden'" aria-controls="map-drawer-content" :aria-label="handleLabel"
        @click="toggle" @keydown.up.prevent="step(1)" @keydown.down.prevent="step(-1)"
        @pointerdown="pointerStart" @pointermove="event => move(event.clientX, event.clientY, event)" @pointerup="finish()" @pointercancel="finish(true)">
        <span class="sheet-grip" aria-hidden="true"></span><span v-show="state !== 'hidden'" class="handle-caption">上滑发现更多，下滑隐藏内容</span>
      </button>
      <div id="map-drawer-content" ref="content" class="drawer-content" :inert="state === 'hidden'" :aria-hidden="state === 'hidden' ? true : undefined" @touchstart.passive="touchStart" @touchmove="touchMove" @touchend="finish()" @touchcancel="finish(true)">
        <slot />
      </div>
    </aside>
  </Teleport>
</template>

<style scoped>
.activity-drawer { position: absolute; left: 0; right: 0; z-index: 15; display: flex; flex-direction: column; min-height: 0; overflow: hidden; background: #fff; box-shadow: 0 -5px 18px #20304b0a; transition: height 620ms cubic-bezier(.22, 1, .36, 1); }
.activity-drawer.dragging { transition: none; }
.drawer-edge { position: absolute; top: 0; left: 0; width: 100%; height: 3px; pointer-events: none; fill: none; stroke: var(--ink); stroke-width: 1.6; }
.drawer-handle { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 4px; height: 38px; flex: 0 0 38px; border: 0; background: transparent; touch-action: none; cursor: ns-resize; }
.drawer-handle:active { transform: none; }
.drawer-handle:focus-visible { outline-offset: -6px; }
.sheet-grip { width: 32px; height: 3px; border-radius: 70%; background: #8d9b9e; }
.handle-caption { font-size: 9px; line-height: 1; color: var(--muted); }
.drawer-content { flex: 1; min-height: 0; padding: 0 17px 18px; overflow-y: auto; overscroll-behavior: contain; scrollbar-width: thin; }
@media (max-width: 359px) { .drawer-content { padding-left: 15px; padding-right: 15px; } }
@media (prefers-reduced-motion: reduce) { .activity-drawer { transition: none; } }
</style>
