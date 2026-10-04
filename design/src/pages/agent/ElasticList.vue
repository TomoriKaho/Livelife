<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue';
import BScroll from '@better-scroll/core';
import MouseWheel from '@better-scroll/mouse-wheel';

BScroll.use(MouseWheel);
const viewport = ref(null), content = ref(null);
let scroll, observer, resizeFrame, motion;

function refresh() {
  if (!viewport.value || !content.value) return;
  // A one-pixel scroll range enables the same edge bounce for lists shorter than the viewport.
  content.value.style.minHeight = (viewport.value.clientHeight + 1) + 'px';
  scroll?.refresh();
}
function queueRefresh() {
  cancelAnimationFrame(resizeFrame);
  resizeFrame = requestAnimationFrame(refresh);
}
function createScroll() {
  scroll?.destroy();
  refresh();
  const reduced = motion.matches;
  scroll = new BScroll(viewport.value, {
    scrollY: true,
    scrollX: false,
    click: true,
    disableMouse: false,
    disableTouch: false,
    bounce: { top: true, bottom: true, left: false, right: false },
    momentum: !reduced,
    bounceTime: reduced ? 0 : 800,
    swipeTime: reduced ? 0 : 2500,
    swipeBounceTime: reduced ? 0 : 500,
    mouseWheel: { easeTime: reduced ? 0 : 300 },
  });
}
function stop() {
  scroll?.stop();
  scroll?.resetPosition(motion?.matches ? 0 : 800);
}
function keyboard(event) {
  if (event.target !== viewport.value || !scroll || event.ctrlKey || event.metaKey || event.altKey) return;
  const page = viewport.value.clientHeight * .85;
  const delta = { ArrowDown: -40, ArrowUp: 40, PageDown: -page, PageUp: page, ' ': event.shiftKey ? page : -page }[event.key];
  let target;
  if (event.key === 'Home') target = 0;
  else if (event.key === 'End') target = scroll.maxScrollY;
  else if (delta != null) target = scroll.y + delta;
  else return;
  event.preventDefault();
  scroll.stop();
  scroll.scrollTo(0, Math.max(scroll.maxScrollY, Math.min(0, target)), motion.matches ? 0 : 180);
}
function focusItem(event) {
  if (!scroll || event.target === viewport.value) return;
  const box = viewport.value.getBoundingClientRect(), item = event.target.getBoundingClientRect();
  const correction = item.top < box.top ? box.top - item.top : item.bottom > box.bottom ? box.bottom - item.bottom : 0;
  if (correction) scroll.scrollTo(0, Math.max(scroll.maxScrollY, Math.min(0, scroll.y + correction)), 0);
}
function nativeScroll() {
  // Focus navigation may scroll an overflow:hidden wrapper; keep a single scroll position.
  const delta = viewport.value.scrollTop;
  if (!delta || !scroll) return;
  viewport.value.scrollTop = 0;
  scroll.scrollTo(0, Math.max(scroll.maxScrollY, Math.min(0, scroll.y - delta)), 0);
}
onMounted(() => {
  motion = window.matchMedia('(prefers-reduced-motion: reduce)');
  createScroll();
  observer = new ResizeObserver(queueRefresh);
  observer.observe(viewport.value);
  observer.observe(content.value);
  motion.addEventListener('change', createScroll);
});
onBeforeUnmount(() => {
  cancelAnimationFrame(resizeFrame);
  observer?.disconnect();
  motion?.removeEventListener('change', createScroll);
  scroll?.destroy();
});
defineExpose({ stop });
</script>

<template>
  <div ref="viewport" class="elastic-list" tabindex="0" @keydown="keyboard" @focusin="focusItem" @scroll="nativeScroll">
    <div ref="content" class="elastic-list-content"><slot /></div>
  </div>
</template>

<style scoped>
.elastic-list { position: relative; min-height: 0; overflow: hidden; overscroll-behavior: none; touch-action: pan-x pinch-zoom; scrollbar-width: none; }
.elastic-list::-webkit-scrollbar { display: none; }
.elastic-list-content { display: flow-root; }
</style>
