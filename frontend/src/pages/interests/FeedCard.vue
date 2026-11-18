<script setup lang="ts">
import type { ContentArticle } from '../../api/content';
defineProps<{ item: ContentArticle }>();
</script>

<template>
  <article v-sketch class="feed-card sketch sketch-white sketch-cast" data-cast="blue">
    <p class="source">{{ item.source_name || '来源名称缺失' }} · {{ item.platform }}</p>
    <h3>{{ item.title || '未提供标题' }}</h3>
    <p class="excerpt">{{ item.excerpt || '暂无正文摘录' }}</p>
    <p class="date">{{ item.published_at ? `发布于 ${new Date(item.published_at).toLocaleString('zh-CN')}` : '发布时间未知' }}</p>
    <a v-if="item.source_url" :href="item.source_url" target="_blank" rel="noopener noreferrer">阅读原文 ↗</a>
    <span v-else class="source">暂无原文链接</span>
  </article>
</template>

<style scoped>
.feed-card { padding: 16px; background: transparent; overflow-wrap: anywhere; }
.source, .date { color: var(--muted); font-size: 12px; }
h3 { margin: 8px 0; font-size: 17px; font-weight: 500; }
.excerpt { margin: 8px 0; font-size: 14px; line-height: 1.7; white-space: pre-wrap; }
a { display: inline-block; padding: 8px 0; color: #326b98; }
</style>