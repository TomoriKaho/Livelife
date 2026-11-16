<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, watch } from 'vue';
import { RouterLink } from 'vue-router';
import { authState, readAuthToken } from '../../api/auth';
import type { FavoriteItem, FavoriteStatus } from '../../api/favorites';
import { favorites } from '../../state/favorites';
import MoreIcon from './MoreIcon.vue';

const state = favorites.state;
const tabs: { id: FavoriteStatus; label: string }[] = [
  { id: 'upcoming', label: '待开始' }, { id: 'ongoing', label: '进行中' },
  { id: 'ended', label: '已结束' }, { id: 'unknown', label: '时间待定' },
];
const loggedIn = computed(() => { void authState.revision; return Boolean(readAuthToken()); });
const emit = defineEmits<{ remove: [message: string] }>();
async function remove(item: FavoriteItem) {
  if (await favorites.set(item.id, false)) emit('remove', `已移除「${item.title || '未命名活动'}」`);
}
function select(status: FavoriteStatus) { if (state.category !== status) { state.category = status; void favorites.load(); } }
const format = (value: string) => new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', year: 'numeric', month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false }).format(new Date(value));
function time(item: FavoriteItem) {
  if (!item.start_at) return `${item.activity_date || '日期未知'} · 开始时间待定`;
  return `${format(item.start_at)}${item.end_at ? ` – ${format(item.end_at)}` : '（结束时间未知，按时间点分类）'}`;
}
onMounted(() => { if (!state.loading) void favorites.load(); });
watch(() => authState.revision, () => { if (readAuthToken()) void favorites.load(); });
const timer = setInterval(() => { if (!document.hidden && readAuthToken() && !state.loading) void favorites.load(); }, 60_000);
onBeforeUnmount(() => clearInterval(timer));
</script>
<template>
  <section class="favorites-list" aria-label="管理收藏的活动">
    <p class="favorites-lede">喜欢的活动，放在这里慢慢发现。<small>按北京时间及已知起止时间分类；不推测缺失时间。</small></p>
    <p v-if="!loggedIn">登录后可保存并恢复自己的收藏。<RouterLink to="/login">前往登录</RouterLink></p>
    <template v-else>
      <div class="favorite-tabs" role="tablist" aria-label="收藏活动状态">
        <button v-for="tab in tabs" :key="tab.id" v-sketch class="sketch" :data-pencil="state.category === tab.id ? 'yellow' : undefined" type="button" role="tab" :aria-selected="state.category === tab.id" @click="select(tab.id)">{{ tab.label }}<small>{{ state.counts[tab.id] }}</small></button>
      </div>
      <button v-sketch class="reload-favorites sketch" type="button" :disabled="state.loading" @click="favorites.load()">重新加载收藏</button>
      <p v-if="state.loading" role="status">正在加载收藏…</p>
      <p v-if="state.error" role="alert">{{ state.error }}<button type="button" @click="favorites.load()">重试</button></p>
      <div role="tabpanel" :aria-label="tabs.find(tab => tab.id === state.category)?.label">
        <article v-for="item in state.items" :key="item.id" v-sketch class="favorite-card sketch" :aria-label="item.title || '未命名活动'">
          <div class="favorite-meta"><span>{{ item.source_name || item.platform }}</span><small>{{ item.available ? tabs.find(tab => tab.id === item.status)?.label : '内容已不可用 · 收藏时信息' }}</small></div>
          <h2>{{ item.title || '未命名活动' }}</h2>
          <p><MoreIcon name="clock" />{{ time(item) }}</p>
          <p v-if="item.available"><MoreIcon name="pin" />{{ item.location || item.place?.name || '地点未提供' }}</p>
          <p v-else>原活动已被清理或不再可用；这里保留最小识别信息。</p>
          <div class="favorite-actions">
            <RouterLink v-if="item.available && item.place?.building_id" v-sketch class="sketch" data-pencil="blue" :to="{ path: '/map', query: { activity: item.id } }"><MoreIcon name="map" />查看地图</RouterLink>
            <a v-if="item.available && item.source_url" v-sketch class="sketch" data-pencil="yellow" :href="item.source_url" target="_blank" rel="noopener noreferrer">查看原文</a>
            <button v-sketch class="remove-favorite sketch" type="button" :disabled="state.pending[item.id]" :aria-label="`移除收藏：${item.title || '未命名活动'}`" @click="remove(item)">{{ state.pending[item.id] ? '移除中…' : '移除收藏' }}</button>
          </div>
          <p v-if="state.errors[item.id]" role="alert">{{ state.errors[item.id] }}</p>
        </article>
        <div v-if="state.loaded && !state.loading && !state.error && !state.items.length" class="empty-favorites"><MoreIcon name="heart" /><p>这里暂时没有收藏的活动。</p><RouterLink to="/calendar">去日历发现活动</RouterLink></div>
        <button v-if="state.next !== null" v-sketch class="load-more sketch" type="button" :disabled="state.loading" @click="favorites.load(true)">加载更多收藏</button>
      </div>
    </template>
  </section>
</template>
<style scoped>
.favorites-lede { margin: 5px 2px 20px; font-size: 14px; line-height: 1.8; }.favorites-lede small { display: block; color: var(--muted); font-size: 11px; }
.favorite-tabs { display: grid; grid-template-columns: repeat(4,minmax(0,1fr)); gap: 7px; margin-bottom: 12px; }.favorite-tabs button { display: flex; flex-wrap: wrap; align-items: center; justify-content: center; gap: 4px; min-height: 44px; padding: 8px 3px; background: transparent; font-size: 12px; }.favorite-tabs small { font-size: 11px; }
.favorite-card { padding: 14px 13px 12px; margin: 15px 0; }.favorite-meta { display: flex; justify-content: space-between; flex-wrap: wrap; gap: 8px; font-size: 12px; }.favorite-meta small { color: var(--muted); }.favorite-card h2 { margin: 14px 0 10px; font-size: 17px; line-height: 1.5; font-weight: 400; overflow-wrap: anywhere; }.favorite-card p { display: flex; align-items: center; gap: 7px; margin: 7px 0; color: var(--muted); font-size: 12px; line-height: 1.6; overflow-wrap: anywhere; }.more-icon { width: 18px; height: 18px; flex: none; }
.favorite-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; }.favorite-actions a,.favorite-actions button,.reload-favorites,.load-more { display: inline-flex; align-items: center; justify-content: center; gap: 5px; min-height: 44px; padding: 8px 10px; font-size: 12px; text-decoration: none; color: var(--ink); background: transparent; }.favorite-actions .remove-favorite { color: #92333e; }.empty-favorites { display: grid; justify-items: center; gap: 14px; padding: 32px 10px; color: var(--muted); }.empty-favorites p { font-size: 14px; margin: 0; }button:disabled { opacity: .6; }
</style>
