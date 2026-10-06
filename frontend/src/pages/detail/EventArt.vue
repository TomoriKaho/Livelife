<script setup>
defineProps({ name: { type: String, required: true } });
</script>

<template>
  <svg v-if="name === 'camera'" class="art" viewBox="0 0 108 100" aria-hidden="true">
    <path d="M92 18c2 5 3 6 8 8-5 2-6 3-8 8-2-5-3-6-8-8 5-2 6-3 8-8Z" fill="#ffd600" />
    <path d="M18 16l7 3M14 24l8 1" fill="none" stroke="#ffd600" stroke-width="3" stroke-linecap="round" />
    <circle cx="36" cy="30" r="15" fill="#fffdf8" stroke="#20304b" stroke-width="2.2" />
    <circle cx="74" cy="30" r="15" fill="#fffdf8" stroke="#20304b" stroke-width="2.2" />
    <circle cx="36" cy="30" r="6.5" fill="#e25d57" />
    <circle cx="74" cy="30" r="6.5" fill="#e25d57" />
    <circle cx="36" cy="30" r="2" fill="#fffdf8" />
    <circle cx="74" cy="30" r="2" fill="#fffdf8" />
    <path d="M50 24h10M50 36h10" stroke="#e25d57" stroke-width="3.2" stroke-linecap="round" />
    <rect x="20" y="42" width="68" height="30" rx="7" fill="#fffdf8" stroke="#20304b" stroke-width="2.2" />
    <circle cx="54" cy="57" r="10" fill="#7eb6ea" stroke="#20304b" stroke-width="2" />
    <circle cx="54" cy="57" r="4.4" fill="#245888" />
    <circle cx="52" cy="55" r="1.5" fill="#fff" />
    <path d="M54 72v5M38 96l16-19 16 19M44 88h20" fill="none" stroke="#20304b" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" />
  </svg>
  <svg v-else-if="name === 'lecture'" class="art" viewBox="0 0 108 100" aria-hidden="true">
    <path d="M90 16c2 4 3 5 7 7-4 2-5 3-7 7-2-4-3-5-7-7 4-2 5-3 7-7Z" fill="#ffd600" />
    <path d="M24 58c0-16 12-26 30-26s30 10 30 26v8H24Z" fill="#fffdf8" stroke="#20304b" stroke-width="2.2" stroke-linejoin="round" />
    <path d="M54 32V22M42 24h24" fill="none" stroke="#20304b" stroke-width="2.2" stroke-linecap="round" />
    <circle cx="54" cy="46" r="8" fill="#7eb6ea" stroke="#20304b" stroke-width="2" />
    <path d="M34 78h40l6 16H28Z" fill="#fffdf8" stroke="#20304b" stroke-width="2.2" stroke-linejoin="round" />
  </svg>
  <svg v-else-if="name === 'course'" class="art" viewBox="0 0 108 100" aria-hidden="true">
    <path d="M90 18c2 4 3 5 7 7-4 2-5 3-7 7-2-4-3-5-7-7 4-2 5-3 7-7Z" fill="#ffd600" />
    <path d="M22 28h30c6 0 10 4 10 10v40H32c-6 0-10-4-10-10Z" fill="#fffdf8" stroke="#20304b" stroke-width="2.2" stroke-linejoin="round" />
    <path d="M86 28H56c-6 0-10 4-10 10v40h30c6 0 10-4 10-10Z" fill="#fffdf8" stroke="#20304b" stroke-width="2.2" stroke-linejoin="round" />
    <path d="M32 40h12M64 40h12M32 50h12M64 50h12" stroke="#7eb6ea" stroke-width="2.4" stroke-linecap="round" />
  </svg>
  <svg v-else class="art" viewBox="0 0 108 100" aria-hidden="true">
    <path d="M90 16c2 4 3 5 7 7-4 2-5 3-7 7-2-4-3-5-7-7 4-2 5-3 7-7Z" fill="#ffd600" />
    <circle cx="40" cy="36" r="12" fill="#ffd0c8" stroke="#20304b" stroke-width="2.2" />
    <circle cx="70" cy="40" r="10" fill="#ffe9a8" stroke="#20304b" stroke-width="2.2" />
    <path d="M18 82c2-16 10-24 22-24s20 8 22 24" fill="#fffdf8" stroke="#20304b" stroke-width="2.2" stroke-linejoin="round" />
    <path d="M52 82c2-14 8-20 18-20s16 6 18 20" fill="#fffdf8" stroke="#20304b" stroke-width="2.2" stroke-linejoin="round" />
    <circle cx="36" cy="36" r="1.4" fill="#20304b" />
    <circle cx="44" cy="36" r="1.4" fill="#20304b" />
    <circle cx="67" cy="40" r="1.3" fill="#20304b" />
    <circle cx="74" cy="40" r="1.3" fill="#20304b" />
  </svg>
</template>

<style scoped>
.art { width: 100%; height: 100%; overflow: visible; }
</style>
