<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import BScroll from '@better-scroll/core';
import MouseWheel from '@better-scroll/mouse-wheel';
import { compactInputHeight } from './composer-layout.mjs';

BScroll.use(MouseWheel);
const props = defineProps({ modelValue: { type: String, default: '' }, expanded: Boolean });
const emit = defineEmits(['update:modelValue', 'overflow', 'focus', 'blur', 'send']);
const editor = ref(null), viewport = ref(null), content = ref(null), textarea = ref(null), mirror = ref(null);
let scroll, observer, frame, motion, revealOnRefresh = false;

function revealCaret() {
  if (!scroll || document.activeElement !== textarea.value) return;
  // An identically wrapped mirror locates the native caret without modifying the draft or selection.
  const caret = textarea.value.selectionDirection === 'backward' ? textarea.value.selectionStart : textarea.value.selectionEnd;
  mirror.value.replaceChildren(document.createTextNode(props.modelValue.slice(0, caret)));
  const marker = document.createElement('span');
  marker.textContent = '\u200b'; mirror.value.append(marker);
  const y = Math.floor((marker.getBoundingClientRect().top - mirror.value.getBoundingClientRect().top) / 24) * 24;
  const height = viewport.value.clientHeight, margin = 0;
  let target = scroll.y;
  if (y + target < margin) target = margin - y;
  else if (y + 24 + target > height - margin) target = height - margin - y - 24;
  scroll.stop();
  scroll.scrollTo(0, Math.max(scroll.maxScrollY, Math.min(0, target)), 0);
}
function refresh() {
  if (!textarea.value || !viewport.value) return;
  const area = textarea.value;
  area.style.height = '0px';
  const textHeight = area.scrollHeight;
  if (!props.expanded) editor.value.style.height = `${compactInputHeight(textHeight + 20, 24, 20)}px`;
  else editor.value.style.removeProperty('height');
  area.style.height = `${Math.max(textHeight, viewport.value.clientHeight)}px`;
  content.value.style.minHeight = `${viewport.value.clientHeight + 1}px`;
  emit('overflow', textHeight > 3 * 24 + 1);
  scroll?.refresh();
  // Resizing an editor preserves its scroll position; typing/navigation reveals the caret.
  if (revealOnRefresh) revealCaret();
  else scroll?.resetPosition(0);
  revealOnRefresh = false;
}
function queueRefresh(reveal = false) {
  revealOnRefresh ||= reveal;
  cancelAnimationFrame(frame); frame = requestAnimationFrame(refresh);
}
function createScroll() {
  scroll?.destroy(); refresh();
  const reduced = motion.matches;
  scroll = new BScroll(viewport.value, {
    scrollY: true, scrollX: false, disableMouse: true, disableTouch: false,
    // Keep native tapping, selection and IME; take over vertical touch movement only.
    tagException: {}, autoBlur: false,
    bounce: { top: true, bottom: true, left: false, right: false }, momentum: !reduced,
    bounceTime: reduced ? 0 : 800, swipeTime: reduced ? 0 : 2500,
    swipeBounceTime: reduced ? 0 : 500, mouseWheel: { easeTime: reduced ? 0 : 300 },
  });
}
function input(event) { emit('update:modelValue', event.target.value); nextTick(() => queueRefresh(true)); }
function focus() { textarea.value?.focus({ preventScroll: true }); }
function focused(event) { emit('focus', event); queueRefresh(true); }
function keyboard(event) {
  if ((event.ctrlKey || event.metaKey) && event.key === 'Enter' && !event.isComposing) { event.preventDefault(); emit('send'); }
  else if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'Home', 'End', 'PageUp', 'PageDown'].includes(event.key)) nextTick(() => queueRefresh(true));
}
function nativeScroll() {
  const delta = viewport.value.scrollTop;
  if (!delta || !scroll) return;
  viewport.value.scrollTop = 0;
  scroll.scrollTo(0, Math.max(scroll.maxScrollY, Math.min(0, scroll.y - delta)), 0);
}
watch(() => props.modelValue, () => nextTick(() => queueRefresh(true)));
watch(() => props.expanded, () => nextTick(() => queueRefresh(true)));
onMounted(() => {
  motion = window.matchMedia('(prefers-reduced-motion: reduce)'); createScroll();
  observer = new ResizeObserver(() => queueRefresh()); observer.observe(editor.value);
  document.fonts?.ready.then(() => { if (textarea.value) queueRefresh(); });
  motion.addEventListener('change', createScroll);
});
onBeforeUnmount(() => { cancelAnimationFrame(frame); observer?.disconnect(); motion?.removeEventListener('change', createScroll); scroll?.destroy(); });
defineExpose({ focus });
</script>

<template>
  <div id="lili-draft-editor" ref="editor" class="elastic-editor" :class="{ expanded }">
    <div ref="viewport" class="editor-viewport" @scroll="nativeScroll">
    <div ref="content" class="editor-content">
      <textarea ref="textarea" :value="modelValue" rows="1" placeholder="想聊点什么？" aria-label="输入给 LiLi 的消息" @input="input" @focus="focused" @blur="emit('blur', $event)" @keydown="keyboard" @compositionend="queueRefresh(true)"></textarea>
    </div>
    <div ref="mirror" class="caret-mirror" aria-hidden="true"></div>
    </div>
  </div>
</template>

<style scoped>
.elastic-editor { position: relative; display: flex; flex-direction: column; flex: 1; min-width: 0; height: 44px; padding: 10px 0; }
.elastic-editor.expanded { height: auto; min-height: 0; width: 100%; }
.editor-viewport { position: relative; flex: 1; min-height: 0; overflow: hidden; overscroll-behavior: none; touch-action: pan-x pinch-zoom; }
.editor-content { display: flow-root; }
textarea,.caret-mirror { display: block; box-sizing: border-box; width: 100%; margin: 0; border: 0; padding: 0; font: inherit; font-size: 16px; line-height: 24px; letter-spacing: normal; color: var(--ink); white-space: pre-wrap; overflow-wrap: break-word; word-break: normal; }
textarea { resize: none; overflow: hidden; background: transparent; outline: none; border-radius: 0; scrollbar-width: none; }
textarea::-webkit-scrollbar { display: none; }
textarea::placeholder { color: var(--muted); }
.caret-mirror { position: absolute; top: 0; left: 0; visibility: hidden; pointer-events: none; }
.expanded textarea,.expanded .caret-mirror { padding-right: 44px; }
</style>
