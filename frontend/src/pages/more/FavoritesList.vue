<script setup>
import { computed, ref } from 'vue';
import { RouterLink } from 'vue-router';
import { categories } from '../../data/activities.js';
import { activityStatus, favoriteTabs, savedActivities, removeSaved, activityMapRoute, activityDetailRoute } from '../../data/favorites.js';
import MoreIcon from './MoreIcon.vue';
const active = ref('upcoming');
const grouped = computed(() => Object.fromEntries(favoriteTabs.map(tab => [tab.id,
  savedActivities.value.filter(item => activityStatus(item) === tab.id)
    .sort((a, b) => `${a.date} ${a.start}`.localeCompare(`${b.date} ${b.start}`))])));
const emit = defineEmits(['remove']);
function remove(item) { removeSaved(item.id); emit('remove', `已移除「${item.title}」`); }
</script>

<template>
  <section class="favorites-list" aria-label="管理收藏的活动">
    <p class="favorites-lede">喜欢的活动，放在这里慢慢发现。<small>演示时间：10月3日 15:00</small></p>
    <div class="favorite-tabs" role="tablist" aria-label="收藏活动状态">
      <button v-for="tab in favoriteTabs" :id="`favorite-tab-${tab.id}`" :key="tab.id" v-sketch class="sketch" :data-pencil="active === tab.id ? tab.pencil : undefined" type="button" role="tab" :aria-selected="active === tab.id" aria-controls="favorite-panel" @click="active = tab.id">{{ tab.label }}<small>{{ grouped[tab.id].length }}</small></button>
    </div>
    <div id="favorite-panel" role="tabpanel" :aria-labelledby="`favorite-tab-${active}`">
      <article v-for="item in grouped[active]" :key="item.id" v-sketch class="favorite-card sketch" :aria-label="item.title">
        <div class="favorite-meta"><span v-sketch class="category-tag sketch" :data-pencil="categories[item.category].pencil">{{ item.label }}</span><small>{{ favoriteTabs.find(tab => tab.id === active).label }}</small></div>
        <h2>{{ item.title }}</h2>
        <p><MoreIcon name="clock" />{{ item.date.slice(5).replace('-', '月') }}日 · {{ item.time }}</p>
        <p><MoreIcon name="pin" />{{ item.place }}</p>
        <div class="favorite-actions">
          <RouterLink v-sketch class="sketch" data-pencil="blue" :to="activityMapRoute(item)"><MoreIcon name="map" /><span>跳转至地图页</span></RouterLink>
          <RouterLink v-sketch class="sketch" data-pencil="yellow" :to="activityDetailRoute(item)"><MoreIcon name="detail" /><span>跳转至详情页</span></RouterLink>
          <button class="remove-favorite" type="button" :aria-label="`移除收藏：${item.title}`" title="移除收藏" @click="remove(item)"><MoreIcon name="trash" /></button>
        </div>
      </article>
      <div v-if="!grouped[active].length" class="empty-favorites"><MoreIcon name="heart" /><p>这里暂时没有收藏的活动。</p><RouterLink v-sketch class="sketch" data-pencil="yellow" to="/calendar">去日历发现活动</RouterLink></div>
    </div>
  </section>
</template>

<style scoped>
.favorites-lede { margin: 5px 2px 20px; font-size: 14px; line-height: 1.8; }.favorites-lede small { display: block; margin-top: 5px; color: var(--muted); font-size: 11px; }
.favorite-tabs { display: grid; grid-template-columns: repeat(3,minmax(0,1fr)); gap: 8px; margin-bottom: 19px; }.favorite-tabs button { display: flex; align-items: center; justify-content: center; gap: 6px; min-height: 44px; padding: 8px 4px; background: transparent; font-size: 13px; }.favorite-tabs small { font-size: 11px; }
.favorite-card { padding: 14px 13px 12px; margin-bottom: 15px; }.favorite-meta { display: flex; align-items: center; justify-content: space-between; gap: 8px; }.category-tag { padding: 4px 10px; font-size: 11px; }.favorite-meta>small { color: var(--muted); font-size: 11px; }.favorite-card h2 { margin: 14px 0 10px; font-size: 17px; line-height: 1.5; font-weight: 400; overflow-wrap: anywhere; }.favorite-card p { display: flex; align-items: center; gap: 7px; margin: 7px 0; color: var(--muted); font-size: 12px; line-height: 1.6; }.favorite-card p .more-icon { width: 17px; height: 17px; }
.favorite-actions { display: grid; grid-template-columns: minmax(0,1fr) minmax(0,1fr) 44px; gap: 7px; margin-top: 14px; }.favorite-actions a { display: flex; align-items: center; justify-content: center; gap: 5px; min-height: 44px; padding: 7px 4px; font-size: 11px; text-decoration: none; color: var(--ink); }.favorite-actions a .more-icon { width: 17px; height: 17px; }.remove-favorite { display: grid; place-items: center; width: 44px; height: 44px; border: 0; background: transparent; color: #92333e; }.remove-favorite .more-icon { width: 23px; height: 23px; }
.empty-favorites { display: grid; justify-items: center; gap: 14px; padding: 42px 10px; color: var(--muted); }.empty-favorites>.more-icon { width: 42px; height: 42px; }.empty-favorites p { font-size: 14px; margin: 0; }.empty-favorites a { padding: 12px 18px; color: var(--ink); text-decoration: none; font-size: 13px; }
@media(max-width:359px) { .favorite-card { padding-inline: 10px; }.favorite-actions { gap: 5px; }.favorite-actions a { flex-direction: column; font-size: 10px; gap: 2px; } }
</style>
