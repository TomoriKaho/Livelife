<script setup>
defineProps({ name: { type: String, default: 'me' } });
</script>

<template>
  <svg class="face" viewBox="0 0 64 64" aria-hidden="true">
    <template v-if="name === 'rain'">
      <path d="M15 32c1-16 33-18 35 2-3-2-6 0-8 3-3-8-12-8-16 0-3-4-7-5-11-5Z" fill="#20304b" />
      <path d="M16 31c-1 10 0 16 3 18M48 33c1 9 0 15-3 17" fill="none" stroke="#20304b" stroke-width="3.2" stroke-linecap="round" />
      <circle cx="26" cy="40" r="2.2" fill="#20304b" />
      <circle cx="40" cy="40" r="2.2" fill="#20304b" />
      <path d="M28 48c2.6 2.8 7.4 2.8 10 0" fill="none" stroke="#20304b" stroke-width="2" stroke-linecap="round" />
    </template>
    <template v-else-if="name === 'walk'">
      <path d="M20 30c2-12 22-14 26 0-3 2-6 1-8-2-2 4-8 4-10 0-3 3-6 4-8 2Z" fill="#20304b" />
      <circle cx="27" cy="40" r="2.1" fill="#20304b" />
      <circle cx="39" cy="40" r="2.1" fill="#20304b" />
      <path d="M29 48c2.2 2.4 6.2 2.4 8.4 0" fill="none" stroke="#20304b" stroke-width="2" stroke-linecap="round" />
    </template>
    <template v-else>
      <path d="M21 30c2-11 20-13 24 0-2 2-6 1-8-1-2 3-8 3-10 0-2 2-5 3-6 1Z" fill="#20304b" />
      <circle cx="27" cy="40" r="2.1" fill="#20304b" />
      <circle cx="39" cy="40" r="2.1" fill="#20304b" />
      <path d="M29 48c2.2 2.4 6.2 2.4 8.4 0" fill="none" stroke="#20304b" stroke-width="2" stroke-linecap="round" />
    </template>
  </svg>
</template>

<style scoped>
.face { width: 38px; height: 38px; display: block; }
</style>
