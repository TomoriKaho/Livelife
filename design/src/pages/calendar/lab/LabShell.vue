<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import LabHeader from './LabHeader.vue';
import LabNav from './LabNav.vue';
import './lab.css';

const route = useRoute();
const page = computed(() => route.meta);
const main = ref(null);
const toastVisible = ref(false);
let toastTimer;

function focusTitle() {
  nextTick(() => document.getElementById('page-title')?.focus({ preventScroll: true }));
}
function showNotification() {
  clearTimeout(toastTimer);
  toastVisible.value = true;
  toastTimer = setTimeout(() => { toastVisible.value = false; }, 2600);
}
watch(() => route.fullPath, async () => {
  await nextTick();
  if (main.value) main.value.scrollTop = 0;
  focusTitle();
});
onMounted(focusTitle);
onBeforeUnmount(() => clearTimeout(toastTimer));
</script>

<template>
  <div class="lab-shell">
    <LabHeader @notify="showNotification" />
    <main ref="main" class="page-main">
      <slot />
    </main>
    <LabNav :active="page.nav" />
    <div v-sketch v-show="toastVisible" class="toast sketch" role="status"><span>消息通知区域待设计</span></div>
  </div>
</template>
