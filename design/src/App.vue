<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { RouterView, useRoute, useRouter } from 'vue-router';
import IconSprite from './components/IconSprite.vue';
import AppHeader from './components/AppHeader.vue';
import PageHeading from './components/PageHeading.vue';
import PageFooter from './components/PageFooter.vue';
import BottomNav from './components/BottomNav.vue';

const route = useRoute();
const router = useRouter();
const page = computed(() => route.meta);
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
  updateTitle();
  await nextTick();
  if (main.value) main.value.scrollTop = 0;
  heading.value?.focusTitle();
});
onMounted(updateTitle);
onBeforeUnmount(() => clearTimeout(toastTimer));
</script>

<template>
  <IconSprite />
  <div v-sketch class="phone-shell">
    <AppHeader @notify="showNotification" />
    <main id="main-content" ref="main" class="page-main" :class="{ 'immersive-main': page.immersive }">
      <PageHeading v-if="!page.customHeading" ref="heading" :page="page" @back="goBack" />
      <RouterView />
      <PageFooter v-if="!page.immersive" />
    </main>
    <BottomNav :active="page.nav" />
  </div>
  <div id="toast" v-sketch v-show="toastVisible" class="toast sketch" role="status"><span>消息通知区域待设计</span></div>
</template>
