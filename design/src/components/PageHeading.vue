<script setup>
import { ref } from 'vue';
import AppIcon from './AppIcon.vue';
defineProps({ page: { type: Object, required: true } });
defineEmits(['back']);
const title = ref(null);
defineExpose({ focusTitle: () => title.value?.focus({ preventScroll: true }) });
</script>

<template>
  <div class="page-heading">
    <div class="page-title-group">
      <button id="back-button" v-sketch class="icon-button back-button" type="button" aria-label="返回上一页" :hidden="!page.back" @click="$emit('back')"><AppIcon name="back" /></button>
      <div><p id="page-eyebrow" class="eyebrow">{{ page.eyebrow }}</p><h1 id="page-title" ref="title" tabindex="-1">{{ page.title }}</h1></div>
    </div>
  </div>
</template>
