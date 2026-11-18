<script lang="ts">
export const pageMeta = {
  key: 'interests', id: 'D-05', title: '兴趣广场', placeholder: '公开内容与原文阅读',
  label: 'INTERESTS', eyebrow: '', icon: 'star', accent: 'pink', nav: 'interests',
  back: false, heading: false, footer: false,
};
</script>

<script setup lang="ts">
import { ref } from 'vue';
import FeedCard from './interests/FeedCard.vue';
import { useContentFeed } from './interests/useContentFeed';
const filters = ref({ keyword: '', platform: '', source_name: '' });
const { items, loading, error, nextOffset, reload, loadMore, retry } = useContentFeed(filters);
</script>

<template>
  <section class="interests-page" aria-labelledby="page-title">
    <header><h1 id="page-title">兴趣广场</h1><p class="hint">查看信息库中的公开内容，打开来源原文。</p></header>
    <form class="filters" @submit.prevent="reload">
      <label>搜索内容<input v-model="filters.keyword" type="search" maxlength="500" placeholder="标题、正文或来源关键词" /></label>
      <details>
        <summary>按平台或来源筛选</summary>
        <label>平台标识<input v-model="filters.platform" maxlength="64" placeholder="如 wechat；留空查看全部" /></label>
        <label>来源名称<input v-model="filters.source_name" maxlength="500" placeholder="填写卡片上的完整来源名称" /></label>
        <p class="hint">平台和来源均精确匹配，可组合筛选。</p>
      </details>
      <button v-sketch class="action sketch sketch-white" type="submit">刷新内容</button>
    </form>
    <p class="hint">兴趣推荐、标签筛选、自定义兴趣及文章账号收藏暂未开放。</p>
    <section :aria-busy="loading" aria-label="公开内容列表">
      <p role="status">{{ loading ? '正在读取内容…' : `已显示 ${items.length} 条` }}</p>
      <div class="feed-list"><FeedCard v-for="item in items" :key="item.id" :item="item" /></div>
      <div v-if="error" role="alert"><p>{{ error }}</p><button class="action" type="button" :disabled="loading" @click="retry">重试</button></div>
      <p v-else-if="!loading && !items.length" class="hint">暂无符合条件的内容，请更换关键词或清空筛选。</p>
      <button v-if="nextOffset !== null && !error" class="action" type="button" :disabled="loading" @click="loadMore">{{ loading ? '正在加载…' : '加载更多' }}</button>
    </section>
  </section>
</template>

<style scoped>
.interests-page { display: flex; flex-direction: column; gap: 12px; padding-bottom: 24px; }
h1 { margin: 0; font-size: 26px; text-decoration: underline; text-decoration-color: #ffdf32; text-underline-offset: 6px; }
.hint { color: var(--muted); font-size: 13px; line-height: 1.7; }
.filters, label { display: flex; flex-direction: column; gap: 8px; }
label { margin: 10px 0; font-size: 14px; }
input { box-sizing: border-box; min-width: 0; width: 100%; padding: 12px; border: 1px solid var(--muted); border-radius: 10px; background: transparent; color: var(--ink); font: inherit; }
summary { cursor: pointer; padding: 10px 0; }
.action { padding: 12px 16px; margin: 8px 2px; color: var(--ink); background: transparent; font: inherit; cursor: pointer; }
.action:disabled { opacity: .6; cursor: wait; }
.feed-list { display: flex; flex-direction: column; gap: 14px; }
</style>
