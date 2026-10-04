<script setup>
defineProps({ name: { type: String, required: true } });
const paths = {
  search: 'M14 14a7 7 0 1 1 10 0 7 7 0 0 1-10 0Z M19 19l7 7',
  sliders: 'M6 9h20 M6 16h20 M6 23h20 M12 6v6 M20 13v6 M10 20v6',
  bookmark: 'M9 6.5h14v20l-7-5-7 5Z',
  brain: 'M9 16c0-3.4 2.2-5.6 5-5.8C15 7.4 19 7.6 20 10.4 23.2 10.6 25 13 25 16c0 2.8-1.6 4.8-4 5.6V25H11v-3.4C9.4 20.8 9 18.6 9 16Z M16 11.2V24 M12.4 15.2h3.2 M16.6 18.4h3.4',
  plus: 'M16 7v18 M7 16h18',
  clock: 'M16 7a9 9 0 1 0 .1 18 9 9 0 0 0-.1-18 M16 11v6l4 2',
  spark: 'M8 18 16 4l2.4 8.2L28 16l-8.2 2.2L16 28l-2.2-8.2L4 16Z',
  chevron: 'M12 7q4.8 4 9 9-4.6 5-9 9',
  back: 'M19 6q-7 6-12 10 5.5 5 12 10 M8 16q9-.2 19 0',
  check: 'M6 16q4 3 7 7Q19 15 27 7',
  close: 'M8 8l16 16 M24 8 8 24',
  trash: 'M6 9 Q16 8.6 26 9 M11 8 12 4 20 4 21 8 M8 10 9 27 Q16 28 23 27 L24 10 M13 13 13.5 23 M19 13 18.5 23',
};
</script>

<template>
  <svg class="interest-icon" viewBox="0 0 32 32" aria-hidden="true" focusable="false">
    <path :d="paths[name] || paths.spark" />
  </svg>
</template>

<style scoped>
.interest-icon { width: 18px; height: 18px; flex: none; fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
</style>
