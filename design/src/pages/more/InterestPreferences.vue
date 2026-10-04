<script setup>
import { ref } from 'vue';
import { interests } from '../onboarding/options.js';
import OnboardingIcon from '../onboarding/OnboardingIcon.vue';
import MoreIcon from './MoreIcon.vue';
const props = defineProps({ selected: { type: Array, required: true } });
const emit = defineEmits(['save']);
const picked = ref([...props.selected]);
function toggle(id) { picked.value = picked.value.includes(id) ? picked.value.filter(value => value !== id) : [...picked.value, id]; }
</script>
<template>
  <section class="interest-preferences" aria-label="选择兴趣标签">
    <p class="interest-lede">喜欢什么，就把它圈起来。<br />随时可以回来换一换。</p>
    <div class="interest-options"><button v-for="item in interests" :key="item.id" v-sketch class="interest-option sketch" :data-pencil="picked.includes(item.id) ? item.pencil : undefined" type="button" :aria-pressed="picked.includes(item.id)" @click="toggle(item.id)"><OnboardingIcon :name="item.icon" /><span>{{ item.label }}</span><MoreIcon v-if="picked.includes(item.id)" class="interest-check" name="check" /></button></div>
    <p class="picked-count" aria-live="polite">已选 {{ picked.length }} 项<span v-if="!picked.length"> · 也可以先随便逛逛</span></p>
    <button v-sketch class="save-interests sketch" data-pencil="yellow" type="button" @click="emit('save', picked)">保存兴趣 <MoreIcon name="check" /></button>
  </section>
</template>
<style scoped>
.interest-lede { margin: 8px 2px 25px; font-size: 15px; line-height: 1.9; color: var(--muted); }
.interest-options { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 12px 10px; }
.interest-option { display: flex; align-items: center; justify-content: center; gap: 8px; min-height: 72px; padding: 15px 10px; font-size: 14px; background: transparent; }
.interest-option .ob-icon { width: 23px; height: 23px; }.interest-check { width: 16px; height: 16px; }
.picked-count { margin: 20px 2px 28px; font-size: 13px; color: var(--muted); }
.save-interests { display: flex; align-items: center; justify-content: center; gap: 12px; width: 100%; min-height: 52px; padding: 12px; font-size: 16px; background: transparent; }
.save-interests .more-icon { width: 20px; height: 20px; }
@media(max-width:359px) { .interest-option { gap: 5px; font-size: 13px; padding-inline: 7px; }.interest-option .ob-icon { width: 19px; height: 19px; } }
</style>
