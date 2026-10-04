<script setup>
defineProps({ name: { type: String, required: true } });
const paths = {
  edit: 'M7 21 22 5 Q24 3 27 6 Q30 9 27 11 L13 26 5 28Z M20 7 26 13 M7 21 13 26',
  chevron: 'M12 7 Q16.8 11 21 16 Q16.4 21 12 25',
  back: 'M19 6 Q12 12 7 16 Q12.5 21 19 26 M8 16 Q17 15.8 27 16',
  shield: 'M16 4 Q22 7 27 8 L26 18 Q24 25 16 29 Q8 25 6 18 L5 8 Q11 7 16 4Z M11 16 15 20 22 12',
  bell: 'M6 24 Q9 20 9 14 Q9 6 16 6 Q23 6 23 14 Q23 20 26 24Z M13 28 Q16 31 19 28 M16 3 16 6',
  palette: 'M17 4 Q5 3 4 15 Q3 27 15 28 Q20 28 18 23 Q16 19 22 20 Q30 21 29 14 Q28 5 17 4Z M10 11 10.1 11 M18 9 18.1 9 M24 13 24.1 13 M9 19 9.1 19',
  help: 'M16 4 Q4 4 4 16 Q4 28 16 28 Q28 28 28 16 Q28 4 16 4Z M12 11 Q13 7 18 9 Q22 12 17 15 L16 18 M16 23 16.1 23',
  spark: 'M16 4 Q18 12 21 13 L28 16 Q20 18 19 21 L16 28 Q14 20 11 19 L4 16 Q12 14 13 11Z',
  check: 'M6 16 Q10 19 13 23 Q19 15 27 7',
  heart: 'M16 27 Q4 19 5 12 Q6 4 16 10 Q26 4 27 12 Q28 19 16 27Z',
  logout: 'M14 5 6 5 6 27 14 27 M13 16 28 16 M22 10 28 16 22 22',
};
</script>
<template><svg class="more-icon" viewBox="0 0 32 32" aria-hidden="true" focusable="false"><path :d="paths[name] || paths.spark" /></svg></template>
<style scoped>
.more-icon { width: 24px; height: 24px; flex: none; fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
</style>
