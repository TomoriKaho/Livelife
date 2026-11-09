<script setup>
import yellow from '../../assets/sketch/default/swatch-yellow.png';
import blue from '../../assets/sketch/default/swatch-blue.png';
import mint from '../../assets/sketch/default/swatch-mint.png';
import pink from '../../assets/sketch/default/swatch-pink.png';
import lavender from '../../assets/sketch/default/swatch-lavender.png';
defineProps({ pencil: { type: String, required: true } });
const swatches = { yellow, blue, mint, pink, lavender };
</script>

<template>
  <img class="swatch" :src="swatches[pencil] || swatches.yellow" alt="" aria-hidden="true" draggable="false" width="10" height="10" />
</template>

<style scoped>
.swatch { width: 10px; height: 10px; display: block; flex: none; }
</style>
