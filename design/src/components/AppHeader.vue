<script setup>
import { RouterLink } from 'vue-router';
import AppIcon from './AppIcon.vue';
defineEmits(['notify']);
</script>

<template>
  <header class="app-header">
    <div class="brand-row">
      <RouterLink v-sketch class="brand sketch pencil-fill" data-pencil="yellow" to="/map" aria-label="LiveLife，返回活动地图">
        <span>LiveLife</span>
      </RouterLink>
      <span class="campus"><AppIcon name="pin" />燕园</span>
      <button class="icon-button notification-button" type="button" aria-label="消息通知" @click="$emit('notify')">
        <AppIcon name="bell" /><span class="notification-dot" aria-hidden="true"></span>
      </button>
    </div>
  </header>
</template>
