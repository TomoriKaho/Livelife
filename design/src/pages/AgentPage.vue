<script>
// 本页面的路由、标题与强调色在本文件维护，公共目录自动读取。
export const pageMeta = {
  "key": "agent",
  "id": "D-06",
  "title": "智能助手",
  "placeholder": "Agent 对话页",
  "label": "AGENT",
  "eyebrow": "A LITTLE HELP, A LOT OF IDEAS",
  "icon": "agent",
  "accent": "lavender",
  "nav": "agent",
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
