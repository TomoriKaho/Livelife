<script>
// 本页面的路由、标题与强调色在本文件维护，路由自动读取。
export const pageMeta = {
  "key": "onboarding",
  "id": "D-01",
  "title": "初次见面",
  "placeholder": "登录、授权与兴趣引导",
  "label": "WELCOME",
  "eyebrow": "HELLO, CAMPUS LIFE",
  "icon": "spark",
  "accent": "pink",
  "shell": "focus",
  "back": false
};
</script>

<script setup>
import { nextTick, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import AppIcon from '../components/AppIcon.vue';
import OnboardingHeader from './onboarding/OnboardingHeader.vue';
import AccountStep from './onboarding/AccountStep.vue';
import PermissionStep from './onboarding/PermissionStep.vue';
import InterestStep from './onboarding/InterestStep.vue';

const router = useRouter();
const step = ref(0);
const accountMode = ref('login');
const body = ref(null);
const locationAllowed = ref(false);
const noticeAllowed = ref(false);
const gender = ref('private');
const selectedInterests = ref(['ai', 'film', 'club', 'volunteer']);

const primaryLabel = { 1: '下一步', 2: '开启校园生活' };
const motion = ref('slide-left');
const sliding = ref(false);

function leave() { router.push('/map'); }
function showStep(next) {
  if (sliding.value || next === step.value) return;
  motion.value = next > step.value ? 'slide-left' : 'slide-right';
  sliding.value = true;
  step.value = next;
}
function onPrimary() {
  if (step.value === 1) showStep(2);
  else leave();
}
function onLogin() {
  if (!sliding.value) leave();
}

watch(step, async () => {
  await nextTick();
  if (body.value) body.value.scrollTop = 0;
  document.getElementById('onboarding-title')?.focus({ preventScroll: true });
});
</script>

<template>
  <div class="onboarding">
    <Transition name="mast">
      <OnboardingHeader v-if="step > 0" class="onboarding-mast" :step="step" />
    </Transition>
    <div ref="body" class="onboarding-body">
      <Transition :name="motion" @after-leave="sliding = false">
        <div :key="step" class="step-pane" :class="{ 'has-chrome': step > 0 }">
          <AccountStep v-if="step === 0" v-model:mode="accountMode" @login="onLogin" @register="showStep(1)" />
          <PermissionStep v-else-if="step === 1" v-model:location-allowed="locationAllowed" v-model:notice-allowed="noticeAllowed" />
          <InterestStep v-else v-model:gender="gender" v-model:selected="selectedInterests" />
        </div>
      </Transition>
    </div>
    <Transition name="dock">
      <div v-if="step > 0" class="onboarding-actions" :class="{ 'is-sliding': sliding }">
        <button class="back-step" type="button" @click="showStep(step - 1)">
          <AppIcon name="back" /> 返回上一步
        </button>
        <button v-sketch class="primary sketch pencil-fill" data-pencil="yellow" type="button" @click="onPrimary">
          {{ primaryLabel[step] }} <AppIcon class="forward" name="chevron" />
        </button>
        <button v-if="step === 2" class="skip" type="button" @click="leave">暂时跳过</button>
        <span v-else class="skip-spacer" aria-hidden="true"></span>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.onboarding {
  position: relative;
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: calc(12px + env(safe-area-inset-top, 0px)) 17px calc(8px + env(safe-area-inset-bottom, 0px));
  background-color: #f8f4ea;
}
.onboarding-body { position: relative; flex: 1; min-height: 0; overflow-x: clip; overflow-y: auto; }
.step-pane.has-chrome { padding-top: 48px; }
.onboarding-mast,
.onboarding-actions { position: absolute; z-index: 2; left: 17px; right: 17px; }
.onboarding-mast { top: calc(12px + env(safe-area-inset-top, 0px)); }
.onboarding-actions { bottom: calc(8px + env(safe-area-inset-bottom, 0px)); }
.slide-left-enter-active,
.slide-left-leave-active,
.slide-right-enter-active,
.slide-right-leave-active { transition: transform .32s ease; }
.slide-left-leave-active,
.slide-right-leave-active { position: absolute; top: 0; left: 0; width: 100%; }
.slide-left-enter-from { transform: translateX(100%); }
.slide-left-leave-to { transform: translateX(-100%); }
.slide-right-enter-from { transform: translateX(-100%); }
.slide-right-leave-to { transform: translateX(100%); }
.is-sliding { pointer-events: none; }
.dock-enter-active,
.dock-leave-active,
.mast-enter-active,
.mast-leave-active { transition: transform .32s ease; }
.dock-enter-from,
.dock-leave-to,
.mast-enter-from,
.mast-leave-to { transform: translateX(100%); }
.dock-leave-active { position: absolute; left: 17px; right: 17px; bottom: calc(8px + env(safe-area-inset-bottom, 0px)); }
.mast-leave-active { position: absolute; left: 17px; right: 17px; top: calc(12px + env(safe-area-inset-top, 0px)); }
@media (prefers-reduced-motion: reduce) {
  .slide-left-enter-active,
  .slide-left-leave-active,
  .slide-right-enter-active,
  .slide-right-leave-active,
  .dock-enter-active,
  .dock-leave-active,
  .mast-enter-active,
  .mast-leave-active { transition: none; }
}
.onboarding-actions { display: flex; flex-direction: column; align-items: center; padding-top: 6px; }
.primary { width: 100%; min-height: 52px; margin-top: 2px; padding: 12px 18px; display: flex; align-items: center; justify-content: center; gap: 8px; background: transparent; border: 0; font-size: 18px; }
.forward { width: 18px; height: 18px; transform: rotate(-90deg); }
.back-step { min-height: 44px; margin-top: 2px; padding: 8px 12px; border: 0; background: transparent; color: var(--ink); font-size: 14px; display: inline-flex; align-items: center; gap: 4px; }
.back-step :deep(.icon) { width: 16px; height: 16px; }
.skip, .skip-spacer { min-height: 44px; margin-top: 2px; }
.skip { padding: 8px 12px; border: 0; background: transparent; color: var(--muted); font-size: 13px; text-decoration: underline; text-underline-offset: 3px; }
@media (max-width: 359px) {
  .onboarding { padding-left: 15px; padding-right: 15px; }
  .onboarding-mast, .onboarding-actions, .dock-leave-active, .mast-leave-active { left: 15px; right: 15px; }
  .primary { font-size: 16px; }
}
</style>
