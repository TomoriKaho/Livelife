<script>
// 本页面的路由、标题与强调色在本文件维护，路由自动读取。
export const pageMeta = {
  "key": "calendar",
  "id": "D-04",
  "title": "活动日历",
  "placeholder": "日历 / 活动列表页",
  "label": "CALENDAR",
  "eyebrow": "MAKE ROOM FOR GOOD DAYS",
  "icon": "calendar",
  "accent": "mint",
  "nav": "calendar",
  "back": false
};
</script>

<script setup>
import PagePlaceholder from '../components/PagePlaceholder.vue';
</script>

<template>
  <!-- 在本文件替换占位内容，页眉、标题栏、页脚与 Tab 由 App.vue 提供。 -->
  <PagePlaceholder :page="pageMeta" />
</template>

<style scoped>
/* 后续本页专属样式放在这里，继承 DESIGN.md 中的公共视觉基线。 */
</style>
