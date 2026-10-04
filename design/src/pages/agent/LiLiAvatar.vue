<script setup>
import { useId } from 'vue';
defineProps({ thinking: Boolean });
const paint = `lili-paint-${useId().replace(/:/g, '')}`;
</script>

<template>
  <svg class="lili-avatar" :class="{ thinking }" viewBox="0 0 108 112" role="img" aria-label="张开双手打招呼的可爱机器人 LiLi" focusable="false">
    <defs><pattern :id="paint" width="9" height="9" patternUnits="userSpaceOnUse" patternTransform="rotate(-30)"><path d="M0 2h9 M0 6h9" stroke="#68758b" stroke-width="2.4" opacity=".12" /></pattern></defs>
    <g stroke="#20304b" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
      <path fill="#d9c8f3" d="M37 64q-6 3-10 12L15 62l-7 7q9 20 21 20l9-10 M71 65q8 4 12 13l12-16 7 7Q94 90 81 89l-9-9" />
      <path fill="#fff1d7" d="M14 67q-9-1-10-6l2-7q2-2 3 2l1 3q-1-13 3-12l2 10q3-8 5-5l-2 9q5-4 5-1l-4 6Z M96 68q10-1 9-7l-2-6q-2-2-3 2l-1 3q1-11-2-11l-2 10q-4-7-5-4l3 8q-5-3-5 0l4 5Z" />
      <path fill="#9ac8f2" d="M37 66q16-8 35 1l7 26q-18 12-48 0Z" />
      <path fill="#d9c8f3" d="m33 71 12 9 9-8 10 8 11-9-4-10H38Z" />
      <path fill="#fff1d7" d="m40 95-3 11q8 5 14-1l2-8 M60 97l3 10q10 2 12-3l-5-10" />
      <path fill="#fff1d7" d="M25 28q-3-17 28-18 30-1 31 18l1 25q-4 17-31 18-26-1-30-17Z" />
      <path fill="#d9c8f3" d="M23 34q-4-20 15-25 30-8 45 9l5 16-13-8-4-7-12 9-9-7-16 12 1-10Z" />
      <path fill="#fff1d7" d="M24 34q-13-4-12 11 1 11 12 8 M85 35q11-4 11 10 0 11-10 9" />
      <path fill="#9ac8f2" d="M31 35q23-8 47 0l1 16q-23 14-48 0Z" />
      <path fill="none" stroke="#fff" stroke-width="2.8" d="m38 40 8-2 M69 54l5-2" opacity=".65" />
      <path fill="#20304b" stroke="none" d="M41 43q3-4 5 0v7q-2 4-5 0Z M62 43q3-4 5 0v7q-2 4-5 0Z" />
      <path class="lili-smile" fill="none" d="M49 53q5 5 10 0" />
      <path fill="none" stroke="#e99796" stroke-width="3" d="m32 55 5 1 M73 55l4-1" opacity=".7" />
      <path fill="#ffdf32" d="m48 3 4 5 8-2-1 8-10-1Z" />
      <circle cx="54" cy="86" r="4" fill="#ffdf32" /><path fill="none" stroke="#fff" d="m53 84 2 3" />
      <path :fill="`url(#${paint})`" stroke="none" d="M25 28q-3-17 28-18 30-1 31 18l1 25q-4 17-31 18-26-1-30-17Z M37 66q16-8 35 1l7 26q-18 12-48 0Z" />
      <path fill="none" stroke-width=".6" opacity=".3" d="M26 29q-2-17 27-17 M38 68q15-8 33 1 M29 89l9-11" />
    </g>
  </svg>
</template>

<style scoped>
.lili-avatar { display: block; width: 100%; height: 100%; overflow: visible; }
.thinking .lili-smile { stroke-dasharray: 2 2; }
</style>
