<script setup>
defineProps({ name: { type: String, required: true } });
const paths = {
  menu: 'M5 8h22 M4 16h23 M5 24h22',
  plus: 'M16 6v20 M6 16h20',
  close: 'm8 8 16 16 M24 8 8 24',
  send: 'm16 3 11 25-11-6L5 28Z M16 22V10',
  copy: 'M12 11h14v17H12Z M21 7V4H5v18h3',
  edit: 'm7 21 15-16q2-2 5 1t1 4L13 26l-9 2Z M20 7l6 6 M7 21l6 5',
  withdraw: 'm12 5-7 7 7 7 M6 12h13q8 0 8 7t-8 7h-4',
  regenerate: 'M27 13a11 11 0 0 0-19-5L4 12 M4 5v7h7 M5 19a11 11 0 0 0 19 5l4-4 M21 20h7v7',
  like: 'M11 14 17 4q4-1 3 4l-1 6h7q3 0 2 4l-3 10H11Z M4 14h7v14H4Z',
  dislike: 'M11 18 17 28q4 1 3-4l-1-6h7q3 0 2-4L25 4H11Z M4 4h7v14H4Z',
  image: 'M4 6h24v21H4Z M5 24l8-9 6 7 4-5 5 6 M21 10a2 2 0 1 1 0 .1',
  file: 'M7 3h12l7 7v19H7Z M19 3v8h7 M12 17h9 M12 23h9',
  chat: 'M5 5h22v18H14l-7 5v-5H5Z M10 11h12 M10 16h8',
  chevron: 'm12 7 9 9-9 9',
  check: 'm7 16 6 6L26 8',
};
</script>

<template>
  <svg class="agent-icon" viewBox="0 0 32 32" aria-hidden="true" focusable="false"><path :d="paths[name] || paths.chat" /></svg>
</template>

<style scoped>
.agent-icon { width: 24px; height: 24px; flex: none; fill: none; stroke: currentColor; stroke-width: 1.7; stroke-linecap: round; stroke-linejoin: round; }
</style>
