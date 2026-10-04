<script setup>
defineProps({ name: { type: String, required: true } });

const icons = {
  speaker: ['M6 12.2h5.2L19 7v18l-7.8-5.2H6Z', 'M22 12.4a4.2 4.2 0 0 1 0 7.2'],
  people: ['M12 13.5a2.6 2.6 0 1 0-.1 0', 'M7 24c.7-4.2 2.8-6.2 5-6.2s4.3 2 5 6.2', 'M21 14.2a2.2 2.2 0 1 0 .1 0', 'M19.2 24c.5-3.4 2-5.2 4-5.2 1.8 0 3.2 1.6 3.8 5.2'],
  music: ['M13 24V11l12-3v13', 'M10 24.5a2.6 2.6 0 1 0 .1 0', 'M22 21.5a2.6 2.6 0 1 0 .1 0'],
  clock: ['M16 7a9 9 0 1 0 .1 18 9 9 0 0 0-.1-18', 'M16 11v6l4 2'],
  bookmark: ['M9 6.5h14v20l-7-5-7 5Z'],
};
</script>

<template>
  <svg class="cal-icon" viewBox="0 0 32 32" aria-hidden="true">
    <path v-for="(d, index) in icons[name]" :key="index" :d="d" />
  </svg>
</template>

<style scoped>
.cal-icon { width: 18px; height: 18px; fill: none; stroke: currentColor; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; flex: none; }
</style>
