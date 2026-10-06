<script setup>
import BalloonArt from './BalloonArt.vue';

defineProps({ step: { type: Number, required: true } });
</script>

<template>
  <header class="welcome-header">
    <div v-sketch class="welcome-brand sketch pencil-fill" data-pencil="yellow">
      <BalloonArt compact />
      <span class="word">LiveLife</span>
    </div>
    <p v-sketch class="step-badge sketch">初次设置 {{ step }}/2</p>
  </header>
</template>

<style scoped>
.welcome-header { container-type: inline-size; display: flex; align-items: center; justify-content: space-between; gap: 8px; flex: none; }
.welcome-brand { display: inline-flex; align-items: center; gap: 6px; min-width: 0; padding: 7px 12px 8px; background: transparent; }
.word { font-size: clamp(14px, 4.6cqi, 20px); letter-spacing: -.5px; line-height: 1.1; white-space: nowrap; -webkit-text-stroke: .12px var(--ink); }
.step-badge { margin: 0; flex: none; padding: 9px 14px; font-size: 13px; line-height: 1.2; background: transparent; }
</style>
