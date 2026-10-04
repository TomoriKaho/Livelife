<script setup>
import { ref } from 'vue';
import AppIcon from '../../components/AppIcon.vue';
import BalloonArt from './BalloonArt.vue';
import OnboardingIcon from './OnboardingIcon.vue';

const emit = defineEmits(['login', 'register']);
const mode = defineModel('mode', { type: String, default: 'login' });
const modes = [
  { id: 'login', label: '登录' },
  { id: 'register', label: '注册' },
];
const username = ref('');
const password = ref('');
const confirmPassword = ref('');
const remember = ref(true);
const showPassword = ref(false);
const showConfirm = ref(false);

function submit() {
  emit(mode.value === 'login' ? 'login' : 'register');
}
</script>

<template>
  <form class="account" @submit.prevent="submit">
    <BalloonArt class="hero" />
    <div class="hero-title">
      <AppIcon class="title-spark" name="spark" />
      <h1 id="onboarding-title" tabindex="-1">欢迎来到 PKULiveLife</h1>
      <AppIcon class="title-spark is-right" name="spark" />
      <svg class="title-underline" viewBox="0 0 140 16" aria-hidden="true"><path d="M6 10c16-6 30 4 46-2s28 4 42-3 28 3 40-4" /></svg>
    </div>

    <div v-sketch class="mode-switch sketch sketch-white sketch-cast" role="tablist" aria-label="登录或注册">
      <button
        v-for="item in modes"
        :key="`${item.id}-${mode === item.id}`"
        v-sketch
        class="mode-tab"
        :class="mode === item.id ? 'sketch pencil-fill' : ''"
        :data-pencil="mode === item.id ? 'blue' : undefined"
        type="button"
        role="tab"
        :aria-selected="mode === item.id"
        @click="mode = item.id"
      >{{ item.label }}</button>
    </div>

    <div class="field">
      <div class="field-head">
        <label for="account-username">用户名</label>
        <span class="required">必填</span>
      </div>
      <span v-sketch class="control sketch sketch-white">
        <OnboardingIcon name="person" />
        <span class="rule" aria-hidden="true"></span>
        <input id="account-username" v-model="username" type="text" name="username" autocomplete="username" placeholder="请输入用户名">
      </span>
    </div>

    <div class="field">
      <div class="field-head">
        <label for="account-password">密码</label>
        <button v-if="mode === 'login'" class="forgot" type="button">忘记密码?</button>
        <span v-else class="required">必填</span>
      </div>
      <span v-sketch class="control sketch sketch-white">
        <OnboardingIcon name="lock" />
        <span class="rule" aria-hidden="true"></span>
        <input id="account-password" v-model="password" :type="showPassword ? 'text' : 'password'" name="password" :autocomplete="mode === 'login' ? 'current-password' : 'new-password'" placeholder="请输入密码">
        <button class="peek" type="button" :aria-pressed="showPassword" :aria-label="showPassword ? '隐藏密码' : '显示密码'" @click="showPassword = !showPassword">
          <OnboardingIcon :name="showPassword ? 'eye-off' : 'eye'" />
        </button>
      </span>
    </div>

    <div v-if="mode === 'register'" class="field">
      <div class="field-head">
        <label for="account-confirm">确认密码</label>
        <span class="required">必填</span>
      </div>
      <span v-sketch class="control sketch sketch-white">
        <OnboardingIcon name="lock" />
        <span class="rule" aria-hidden="true"></span>
        <input id="account-confirm" v-model="confirmPassword" :type="showConfirm ? 'text' : 'password'" name="confirm-password" autocomplete="new-password" placeholder="请再次输入密码">
        <button class="peek" type="button" :aria-pressed="showConfirm" :aria-label="showConfirm ? '隐藏确认密码' : '显示确认密码'" @click="showConfirm = !showConfirm">
          <OnboardingIcon :name="showConfirm ? 'eye-off' : 'eye'" />
        </button>
      </span>
    </div>

    <label v-if="mode === 'login'" class="remember">
      <input v-model="remember" type="checkbox">
      记住登录状态
    </label>
    <span v-else class="remember-spacer" aria-hidden="true"></span>

    <button v-sketch class="enter sketch pencil-fill" data-pencil="yellow" type="submit">
      {{ mode === 'login' ? '登录并进入' : '注册并继续' }} <AppIcon class="forward" name="chevron" />
    </button>
  </form>
</template>

<style scoped>
.account { display: flex; flex-direction: column; width: 100%; padding: 8px 0 12px; }
.hero { margin: 10px auto 8px; }
.hero-title { position: relative; display: flex; align-items: center; justify-content: center; gap: 8px; margin-bottom: 22px; }
.hero-title h1 { font-size: 24px; text-align: center; }
.title-spark { width: 16px; height: 16px; color: #f2c431; }
.is-right { transform: rotate(18deg); }
.title-spark:not(.is-right) { transform: rotate(-16deg); }
.title-underline { position: absolute; left: 54%; bottom: -4px; width: 128px; height: 14px; fill: none; stroke: #ffdf32; stroke-width: 3.2; stroke-linecap: round; }
.mode-switch { display: grid; grid-template-columns: 1fr 1fr; width: min(248px, 74%); margin: 0 auto 22px; padding: 4px; background: transparent; }
.mode-tab { min-height: 42px; border: 0; background: transparent; font-size: 16px; color: var(--ink); }
.field { margin-bottom: 16px; }
.field-head { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin: 0 2px 8px; font-size: 16px; }
.required { color: #a3adbd; font-size: 13px; }
.forgot { border: 0; background: transparent; color: #e06a32; font: inherit; font-size: 14px; padding: 0; }
.control { display: flex; align-items: center; gap: 8px; width: 100%; min-height: 52px; padding: 0 6px 0 14px; background: transparent; color: var(--ink); }
.rule { width: 1px; align-self: stretch; margin: 14px 2px; background: #c5ceda; }
.control input { flex: 1; min-width: 0; min-height: 48px; border: 0; background: transparent; font: inherit; font-size: 16px; color: var(--ink); padding: 0; }
.control input::placeholder { color: #9aa6b8; }
.control input:focus, .control input:focus-visible { outline: none; }
.peek { width: 40px; height: 40px; border: 0; background: transparent; color: var(--ink); display: grid; place-items: center; padding: 0; flex: none; }
.remember, .remember-spacer { display: flex; align-items: center; min-height: 18px; margin: 2px 0 22px; }
.remember { gap: 8px; width: fit-content; font-size: 15px; }
.remember input { appearance: none; width: 18px; height: 18px; margin: 0; border: 1.6px solid var(--ink); border-radius: 4px; background: #fff; display: grid; place-items: center; flex: none; }
.remember input:checked { background: var(--ink); }
.remember input:checked::after { content: ''; width: 8px; height: 4px; border-left: 2px solid #fff; border-bottom: 2px solid #fff; transform: translateY(-1px) rotate(-45deg); }
.remember input:focus-visible { outline: 3px solid #456e99; outline-offset: 3px; }
.enter { width: 100%; min-height: 52px; border: 0; background: transparent; font-size: 18px; display: flex; align-items: center; justify-content: center; gap: 8px; }
.forward { width: 18px; height: 18px; transform: rotate(-90deg); }
@media (max-width: 359px) {
  .hero-title h1 { font-size: 21px; }
  .title-underline { width: 108px; left: 52%; }
  .mode-tab, .enter, .control input, .field-head { font-size: 15px; }
}
</style>
