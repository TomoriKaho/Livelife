<script setup>
import AppIcon from './AppIcon.vue';
defineProps({ page: { type: Object, required: true } });
</script>

<template>
  <section id="page-outlet" v-sketch class="page-outlet" :data-page="page.key" :style="{ '--page-accent': `var(--${page.accent})` }" aria-labelledby="placeholder-title">
    <span id="page-code" class="page-code">{{ page.id }} / {{ page.label }}</span>
    <div class="placeholder">
      <div class="placeholder-art" aria-hidden="true">
        <span v-sketch class="art-paper sketch pencil-fill" :data-pencil="page.accent"><AppIcon :name="page.icon" /></span>
        <AppIcon class="art-spark" name="spark" /><span class="art-dash"></span>
      </div>
      <p class="placeholder-kicker">留一点空白，给接下来的灵感</p>
      <h2 id="placeholder-title">{{ page.placeholder }}</h2>
      <p class="placeholder-description">页面内容待设计</p>
      <span class="placeholder-rule" aria-hidden="true"></span>
    </div>
    <span class="outlet-corner" aria-hidden="true"><AppIcon name="pencil" /></span>
  </section>
</template>
