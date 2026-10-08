<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { RouterView, useRoute, useRouter } from 'vue-router';
import IconSprite from './components/IconSprite.vue';
import AppHeader from './components/AppHeader.vue';
import PageHeading from './components/PageHeading.vue';
import PageFooter from './components/PageFooter.vue';
import BottomNav from './components/BottomNav.vue';

const route = useRoute();
const props = defineProps({ warming: { type: Boolean, default: false } });
const router = useRouter();
const page = computed(() => route.meta);
const focusShell = computed(() => page.value.shell === 'focus');
const main = ref(null);
const heading = ref(null);
const toastVisible = ref(false);
let toastTimer;

function goBack() {
  if (router.options.history.state.back) router.back();
  else router.replace('/map');
}
function showNotification() {
  clearTimeout(toastTimer);
  toastVisible.value = true;
  toastTimer = setTimeout(() => { toastVisible.value = false; }, 2600);
}
function updateTitle() { document.title = `${page.value.title || '手机端设计'} · PKU LiveLife`; }
watch(() => route.fullPath, async () => {
  if (props.warming) return;
  updateTitle();
  await nextTick();
  if (main.value) main.value.scrollTop = 0;
  if (heading.value) heading.value.focusTitle();
  else document.getElementById('page-title')?.focus({ preventScroll: true });
});
onMounted(() => { if (!props.warming) updateTitle(); });
onBeforeUnmount(() => clearTimeout(toastTimer));
</script>

<template>
  <IconSprite />
  <div v-sketch class="phone-shell">
    <AppHeader v-if="!focusShell" :class="{ 'map-header': page.key === 'map' }" @notify="showNotification" />
    <main id="main-content" ref="main" class="page-main" :class="{ 'is-focus': focusShell, 'immersive-main': page.immersive, 'map-main': page.key === 'map' }">
      <PageHeading v-if="!focusShell && !page.customHeading && page.heading !== false" ref="heading" :page="page" @back="goBack" />
      <RouterView />
      <PageFooter v-if="!focusShell && !page.immersive && page.footer !== false" />
    </main>
    <BottomNav v-if="!focusShell" :active="page.nav" />
  </div>
  <div id="toast" v-sketch v-show="toastVisible" class="toast sketch" role="status"><span>消息通知区域待设计</span></div>
</template>
