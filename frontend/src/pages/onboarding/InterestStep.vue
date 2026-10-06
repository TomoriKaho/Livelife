<script setup>
import { genders, interests } from './options.js';
import OnboardingIcon from './OnboardingIcon.vue';

const gender = defineModel('gender', { type: String, default: '' });
const selected = defineModel('selected', { type: Array, default: () => [] });

function chooseGender(id) {
  gender.value = gender.value === id ? '' : id;
}
function toggleInterest(id) {
  const next = new Set(selected.value);
  if (next.has(id)) next.delete(id);
  else next.add(id);
  selected.value = interests.filter(item => next.has(item.id)).map(item => item.id);
}
</script>

<template>
  <section class="interest-step" aria-labelledby="onboarding-title">
    <div class="hero-title">
      <span class="title-marks" aria-hidden="true"></span>
      <h1 id="onboarding-title" tabindex="-1">让我们更好了解你吧！</h1>
      <svg class="title-underline" viewBox="0 0 140 16" aria-hidden="true"><path d="M6 10c16-6 30 4 46-2s28 4 42-3 28 3 40-4" /></svg>
    </div>
    <p class="lede">登陆账户后可在设置中修改</p>

    <p id="gender-label" class="field-label">你的性别</p>
    <div class="gender-row" role="radiogroup" aria-labelledby="gender-label">
      <button v-for="item in genders" :key="item.id" v-sketch class="choice sketch sketch-cast" :class="gender === item.id ? 'pencil-fill' : 'sketch-white'" type="button" role="radio" :aria-checked="gender === item.id" :data-pencil="gender === item.id ? item.pencil : undefined" :data-cast="item.pencil" @click="chooseGender(item.id)">
        <OnboardingIcon :name="item.icon" />
        <span class="choice-label">{{ item.label }}</span>
        <span v-if="gender === item.id" class="tick" aria-hidden="true"><svg viewBox="0 0 16 16"><path d="M3.5 8.2 6.6 11.3 12.5 4.8" /></svg></span>
      </button>
    </div>

    <p id="interest-label" class="field-label">你的兴趣</p>
    <div class="interest-grid" role="group" aria-labelledby="interest-label">
      <button v-for="item in interests" :key="item.id" v-sketch class="choice sketch sketch-cast" :class="selected.includes(item.id) ? 'pencil-fill' : 'sketch-white'" type="button" :aria-pressed="selected.includes(item.id)" :data-pencil="selected.includes(item.id) ? item.pencil : undefined" :data-cast="item.pencil" @click="toggleInterest(item.id)">
        <OnboardingIcon :name="item.icon" />
        <span class="choice-label">{{ item.label }}</span>
        <span v-if="selected.includes(item.id)" class="tick" aria-hidden="true"><svg viewBox="0 0 16 16"><path d="M3.5 8.2 6.6 11.3 12.5 4.8" /></svg></span>
      </button>
    </div>
  </section>
</template>

<style scoped>
.interest-step { display: flex; flex-direction: column; padding-top: 40px; }
.hero-title { position: relative; display: flex; align-items: center; justify-content: center; }
h1 { margin: 0; font-size: 28px; text-align: center; }
.title-marks { position: relative; flex: none; width: 7px; height: 3px; margin: 2px 10px 0 0; border-radius: 2px; background: #ffdf32; box-shadow: -1px 8px 0 #ffdf32, 2px 15px 0 #ffdf32; transform: rotate(24deg); }
.title-underline { position: absolute; left: 54%; bottom: -6px; width: 128px; height: 14px; fill: none; stroke: #ffdf32; stroke-width: 3.2; stroke-linecap: round; }
.lede { margin: 10px 0 6px; text-align: center; color: var(--muted); font-size: 13px; line-height: 1.5; }
.field-label { margin: 22px 2px 8px; font-size: 14px; }
.gender-row { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
.interest-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.choice { display: flex; align-items: center; gap: 6px; width: 100%; height: 48px; min-height: 48px; padding: 8px 10px; background: transparent; border: 0; font-size: 14px; text-align: left; color: inherit; }
.choice-label { flex: 1; min-width: 0; }
.tick { width: 16px; height: 16px; border: 1.6px solid var(--ink); border-radius: 50%; display: grid; place-items: center; flex: none; }
.tick svg { width: 12px; height: 12px; fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
@media (max-width: 359px) {
  h1 { font-size: 24px; }
  .choice { font-size: 13px; padding: 8px; gap: 4px; }
}
</style>
