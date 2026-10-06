<script setup>
defineProps({ name: { type: String, required: true } });
</script>

<template>
  <svg class="icon" aria-hidden="true"><use :href="`#icon-${name}`" /></svg>
</template>
