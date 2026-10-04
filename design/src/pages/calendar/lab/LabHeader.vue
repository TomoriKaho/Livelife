<script setup>
import { RouterLink } from 'vue-router';
import AppIcon from '../../../components/AppIcon.vue';
import BalloonArt from '../../onboarding/BalloonArt.vue';
defineEmits(['notify']);
</script>

<template>
  <header class="lab-header">
    <RouterLink v-sketch class="lab-brand sketch pencil-fill" data-pencil="yellow" to="/map" aria-label="PKU LiveLife，返回活动地图">
      <BalloonArt compact />
      <span class="lab-word">PKU<span class="lab-life">LiveLife</span></span>
    </RouterLink>
    <span class="lab-campus"><AppIcon name="pin" />燕园<AppIcon class="lab-caret" name="chevron" /></span>
    <button class="icon-button notification-button lab-bell" type="button" aria-label="消息通知" @click="$emit('notify')">
      <AppIcon name="bell" /><span class="notification-dot" aria-hidden="true"></span>
    </button>
  </header>
</template>
