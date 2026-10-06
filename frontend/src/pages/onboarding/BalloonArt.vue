<script setup>
import logo from '../../pictures/logo4-main-ui-palette-transparent-v3.png';

defineProps({ compact: { type: Boolean, default: false } });
</script>

<template>
  <img class="balloon" :class="{ 'is-compact': compact }" :src="logo" alt="" />
</template>

<style scoped>
.balloon { width: 112px; height: 112px; display: block; object-fit: contain; }
.is-compact { width: 30px; height: 30px; }
</style>
