<script setup>
import { RouterLink } from 'vue-router';
import AppIcon from './AppIcon.vue';
import BalloonArt from '../pages/onboarding/BalloonArt.vue';
defineEmits(['notify']);
</script>

<template>
  <header class="app-header">
    <RouterLink v-sketch class="app-brand sketch pencil-fill sketch-cast" data-pencil="yellow" data-cast="yellow" to="/map" aria-label="LiveLife，返回活动地图">
      <BalloonArt compact />
      <span class="brand-word">LiveLife</span>
    </RouterLink>
    <span class="campus"><AppIcon name="pin" />燕园<AppIcon class="campus-caret" name="chevron" /></span>
    <button class="icon-button notification-button" type="button" aria-label="消息通知" @click="$emit('notify')">
      <AppIcon name="bell" /><span class="notification-dot" aria-hidden="true"></span>
    </button>
  </header>
</template>
