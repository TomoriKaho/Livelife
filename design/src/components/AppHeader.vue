<script setup>
import { RouterLink } from 'vue-router';
import AppIcon from './AppIcon.vue';
defineEmits(['notify']);
</script>

<template>
  <header class="app-header">
    <div class="brand-row">
      <RouterLink v-sketch class="brand sketch pencil-fill" data-pencil="yellow" to="/map" aria-label="PKU LiveLife，返回活动地图">
        <span>PKU<span class="brand-life">LiveLife</span></span>
      </RouterLink>
      <span class="campus"><AppIcon name="pin" />燕园</span>
      <button class="icon-button notification-button" type="button" aria-label="消息通知" @click="$emit('notify')">
        <AppIcon name="bell" /><span class="notification-dot" aria-hidden="true"></span>
      </button>
    </div>
    <div class="header-caption"><span>校园生活 · 随手发现</span><span class="handwritten">Life, in color.</span></div>
  </header>
</template>
