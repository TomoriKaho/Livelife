<script setup>
import { ref } from 'vue';
import { interests } from '../onboarding/options.js';
import OnboardingIcon from '../onboarding/OnboardingIcon.vue';
import MoreIcon from './MoreIcon.vue';
import PreferenceSwitch from './PreferenceSwitch.vue';
const props = defineProps({ selected: { type: Array, required: true }, personalized: Boolean, mode: String });
const emit = defineEmits(['save']);
const picked = ref([...props.selected]);
const enabled = ref(props.personalized), direction = ref(props.mode || 'interest');
const directions = [
  { id: 'interest', title: '兴趣优先', note: '多看看喜欢的事', color: 'blue', icon: 'heart' },
  { id: 'explore', title: '多些新发现', note: '也遇见不一样的事', color: 'mint', icon: 'spark' },
];
function toggle(id) { if (enabled.value) picked.value = picked.value.includes(id) ? picked.value.filter(value => value !== id) : [...picked.value, id]; }
</script>
<template>
  <section class="interest-preferences" aria-label="选择兴趣标签">
    <div class="personalized-row"><span><strong>个性化推荐</strong><small>让校园活动更贴近你的兴趣</small></span><PreferenceSwitch v-model="enabled" label="个性化推荐" /></div>
    <p v-if="!enabled" class="disabled-note" role="status">开启个性化推荐后，再圈选兴趣和推荐方向。<br />之前选好的兴趣会为你保留。</p>
    <p class="interest-lede">喜欢什么，就把它圈起来。<br />随时可以回来换一换。</p>
    <div class="interest-options"><button v-for="item in interests" :key="item.id" v-sketch class="interest-option sketch" :data-pencil="picked.includes(item.id) ? item.pencil : undefined" :disabled="!enabled" type="button" :aria-pressed="picked.includes(item.id)" @click="toggle(item.id)"><OnboardingIcon :name="item.icon" /><span>{{ item.label }}</span><MoreIcon v-if="picked.includes(item.id)" class="interest-check" name="check" /></button></div>
    <p class="picked-count" aria-live="polite">已选 {{ picked.length }} 项<span v-if="!picked.length"> · 也可以先随便逛逛</span></p>
    <h2 class="direction-heading">希望看到什么？</h2>
    <div class="choice-grid" role="group" aria-label="推荐方向"><button v-for="item in directions" :key="item.id" v-sketch class="choice-card sketch" :data-pencil="direction === item.id ? item.color : undefined" :disabled="!enabled" type="button" :aria-pressed="direction === item.id" @click="direction = item.id"><MoreIcon :name="item.icon" /><strong>{{ item.title }}</strong><small>{{ item.note }}</small><MoreIcon v-if="direction === item.id" class="choice-check" name="check" /></button></div>
    <button v-sketch class="save-interests sketch" data-pencil="yellow" type="button" @click="emit('save', { selected: picked, personalized: enabled, mode: direction })">保存设置 <MoreIcon name="check" /></button>
  </section>
</template>
<style scoped>
.personalized-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 9px 2px 18px; border-bottom: 1px solid #20304b22; }.personalized-row strong { display: block; font-size: 16px; font-weight: 400; }.personalized-row small { display: block; margin-top: 7px; font-size: 11px; color: var(--muted); line-height: 1.6; }.disabled-note { margin: 15px 2px; font-size: 12px; color: var(--muted); line-height: 1.8; }
.direction-heading { margin: 0 2px 14px; font-size: 16px; font-weight: 400; }.choice-grid { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 12px; margin-bottom: 24px; }.choice-card { position: relative; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 9px; padding: 16px 6px; min-height: 121px; background: transparent; }.choice-card strong { font-size: 14px; font-weight: 400; }.choice-card small { font-size: 11px; }.choice-check { position: absolute; right: 8px; top: 8px; width: 14px; height: 14px; }.interest-option:disabled,.choice-card:disabled { opacity: .4; cursor: default; }
.interest-lede { margin: 8px 2px 25px; font-size: 15px; line-height: 1.9; color: var(--muted); }
.interest-options { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 12px 10px; }
.interest-option { display: flex; align-items: center; justify-content: center; gap: 8px; min-height: 72px; padding: 15px 10px; font-size: 14px; background: transparent; }
.interest-option .ob-icon { width: 23px; height: 23px; }.interest-check { width: 16px; height: 16px; }
.picked-count { margin: 20px 2px 28px; font-size: 13px; color: var(--muted); }
.save-interests { display: flex; align-items: center; justify-content: center; gap: 12px; width: 100%; min-height: 52px; padding: 12px; font-size: 16px; background: transparent; }
.save-interests .more-icon { width: 20px; height: 20px; }
@media(max-width:359px) { .interest-option { gap: 5px; font-size: 13px; padding-inline: 7px; }.interest-option .ob-icon { width: 19px; height: 19px; } }
</style>
