<script setup lang="ts">
import type { NearbyActivity } from '../../api/information';
import { currentLocation } from '../../platform/location-tracker';
import { distanceMeters } from './useNearbyActivities';

defineProps<{ items: NearbyActivity[]; state: string; message: string; selected: string | null }>();
const radius = defineModel<number>('radius', { required: true });
const keyword = defineModel<string>('keyword', { required: true });
const today = defineModel<boolean>('today', { required: true });
defineEmits<{ select: [id: string | null]; retry: [] }>();
const formatTime = (value: string) => new Date(value).toLocaleString('zh-CN', {
  timeZone: 'Asia/Shanghai', month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit',
});
function sourceUrl(value: string | null) {
  if (!value) return undefined;
  try { const url = new URL(value); return ['https:', 'http:'].includes(url.protocol) ? url.href : undefined; }
  catch { return undefined; }
}
</script>

<template>
  <section class="nearby-results" aria-label="附近活动查询">
    <div class="nearby-heading"><h2>附近活动</h2><button type="button" @click="$emit('retry')">重新定位与刷新</button></div>
    <details class="nearby-filter-panel"><summary>筛选 · {{ radius }} 米 · {{ today ? "仅今天" : "含历史活动" }}{{ keyword ? ` · ${keyword}` : "" }}</summary>
    <div class="nearby-filters">
      <label>范围 <select v-model.number="radius" aria-label="搜索半径"><option :value="100">100 米</option><option :value="300">300 米</option><option :value="500">500 米</option><option :value="1000">1 千米</option></select></label>
      <input v-model="keyword" aria-label="活动关键词" placeholder="搜索活动关键词" maxlength="500">
      <label><input v-model="today" type="checkbox">仅今天（北京时间）</label>
    </div></details>
    <p class="nearby-status" role="status" :data-state="state">{{ message }}</p>
    <p v-if="currentLocation && state === 'waiting'" class="nearby-note">上次定位误差约 {{ Math.round(currentLocation.accuracy) }} 米</p>
    <button v-if="selected" type="button" @click="$emit('select', null)">返回附近全部活动</button>
    <p v-if="selected && state === 'ready' && !items.some(item => item.place.building_id === selected)">该建筑暂无符合条件的活动。</p>
    <article v-for="item in items.filter(item => !selected || item.place.building_id === selected)" :key="item.id" class="nearby-card">
      <span class="source-tag">{{ item.platform === 'demo' ? '合成演示条目' : (item.source_name || '来源公告') }}</span>
      <h3>{{ item.title || '未命名活动' }}</h3>
      <p>{{ formatTime(item.activity_start_at) }}{{ item.activity_end_at ? ` — ${formatTime(item.activity_end_at)}` : '' }}</p>
      <p>{{ item.activity_location || item.place.name }} · {{ currentLocation ? Math.round(distanceMeters(currentLocation, item.place)) : '—' }} 米</p>
      <p class="nearby-note">{{ item.location_resolution?.floor || '楼层未确认' }} · {{ item.location_resolution?.room ? `教室 ${item.location_resolution.room}` : '场地详情见原文' }}</p>
      <details><summary>查看内容</summary><p class="article-content">{{ item.content }}</p></details>
      <div class="nearby-actions"><button v-if="item.place.building_id" type="button" @click="$emit('select', item.place.building_id)">在地图查看</button><a v-if="sourceUrl(item.source_url)" :href="sourceUrl(item.source_url)" target="_blank" rel="noopener noreferrer">打开原文 ↗</a></div>
    </article>
  </section>
</template>

<style scoped>
.nearby-results { padding: 12px 18px 24px; color: #20304b; }
.nearby-heading { display:flex; align-items:center; justify-content:space-between; gap:8px; }
h2 { font-size:20px; margin:4px 0; } h3 { font-size:17px; margin:8px 0; }
p { font-size:13px; line-height:1.6; margin:6px 0; }
.nearby-filter-panel { margin:8px 0; font-size:13px; }
.nearby-note { color:#5c6b76; font-size:12px; }
.nearby-filters { display:flex; flex-wrap:wrap; gap:10px; align-items:center; margin:12px 0; }
.nearby-filters label { font-size:13px; } input, select, button { font:inherit; }
input:not([type=checkbox]) { width:145px; flex:1; min-width:110px; }
select, input:not([type=checkbox]), button { padding:8px; border:1px solid #a7b5c2; border-radius:8px; background:#fffdf5; color:#20304b; }
.nearby-heading button { font-size:12px; } button, a, summary { cursor:pointer; }
.nearby-status { font-weight:600; }.nearby-status[data-state=error] { color:#984838; }
.nearby-card { border:1px solid #d2d7d3; border-radius:12px; padding:14px; background:#fffdf5; margin:12px 0; }
.source-tag { font-size:11px; color:#526575; }.nearby-actions { display:flex; align-items:center; gap:16px; margin-top:12px; font-size:13px; }
.article-content { white-space:pre-wrap; overflow-wrap:anywhere; }
</style>
