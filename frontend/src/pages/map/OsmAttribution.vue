<script setup lang="ts">
import { OSM_ATTRIBUTION_TEXT, OSM_COPYRIGHT_URL } from './osm-attribution';

// 外部版权页交给系统浏览器打开：capacitor.config.ts 不把该域名加入 server.allowNavigation。
// 本组件只负责文案、链接和基础外观；定位由使用方通过 class 提供。
</script>

<template>
  <a class="osm-attribution" :href="OSM_COPYRIGHT_URL" target="_blank" rel="noopener noreferrer">{{ OSM_ATTRIBUTION_TEXT }}</a>
</template>

<style scoped>
.osm-attribution { font: 10px/1.4 system-ui; color: #334; background: #fffC; padding: 2px 4px; border-radius: 3px; }
</style>
