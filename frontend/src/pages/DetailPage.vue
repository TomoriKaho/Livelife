<script>
// 详情不归属任何一个底部 Tab。返回、收藏和评论由本页绘制。
export const pageMeta = {
  key: 'detail',
  id: 'D-03',
  title: '活动详情',
  placeholder: '活动介绍与评论',
  label: 'DETAIL',
  eyebrow: 'A CLOSER LOOK',
  icon: 'pencil',
  accent: 'mint',
  nav: '',
  back: true,
  heading: false,
  footer: false,
};
</script>

<script setup>
import { computed, nextTick, ref, watch } from 'vue';
import { RouterLink, useRoute, useRouter } from 'vue-router';
import AppIcon from '../components/AppIcon.vue';
import AgentIcon from './agent/AgentIcon.vue';
import { activities, categories } from '../data/activities.js';
import CommentFace from './detail/CommentFace.vue';

const inkOf = { yellow: '#ffdf32', blue: '#9ac8f2', mint: '#7ec9a8', pink: '#f4b2ab', lavender: '#c9b6f0' };
const avatarPencils = ['pink', 'yellow', 'blue', 'mint', 'lavender'];
const threads = {
  film: [
    { id: 'rain', name: '未名小雨', face: 'rain', text: '映后交流很有意思，期待这周的片单！', time: '10分钟前' },
    { id: 'me-film', name: '我', face: 'me', text: '我先占了靠过道的位子，映后想聊聊结尾那一场。', time: '1小时前' },
    { id: 'walk', name: '燕园散步者', face: 'walk', text: '讲堂的氛围特别适合看老电影。', time: '刚刚' },
  ],
  ai: [
    { id: 'note', name: '理教占座', face: 'walk', text: '想听他们怎么讲选课和找资料。', time: '2小时前' },
    { id: 'me-ai', name: '我', face: 'me', text: '我想问问写作业时哪些步骤适合交给模型，哪些还是自己来。', time: '40分钟前' },
  ],
  reading: [
    { id: 'me-reading', name: '我', face: 'me', text: '我这周带了一本很薄的散文，想听听别人怎么读开头。', time: '昨天' },
    { id: 'leaf', name: '二教窗边', face: 'rain', text: '我也带了书，到了可以换着讲。', time: '3小时前' },
  ],
  salon: [
    { id: 'ask', name: '跨院同学', face: 'walk', text: '准备听不同专业怎么追问同一篇论文。', time: '昨天' },
    { id: 'me-salon', name: '我', face: 'me', text: '我准备了一页笔记，想听听别的专业会怎么追问。', time: '5小时前' },
  ],
};

const route = useRoute();
const router = useRouter();
const saved = ref(false);
const draft = ref('');
const posted = ref([]);
const scroller = ref(null);

const activityId = computed(() => {
  const value = route.query.id;
  const id = Array.isArray(value) ? value[0] : value;
  return id || 'film';
});
const activity = computed(() => activities.find(item => item.id === activityId.value) || null);
const category = computed(() => activity.value ? categories[activity.value.category] : null);
const kindInk = computed(() => inkOf[category.value?.pencil] || inkOf.yellow);
const comments = computed(() => {
  if (!activity.value) return [];
  const seed = threads[activity.value.id] || [
    { id: 'rain', name: '未名小雨', face: 'rain', text: `想去看看「${activity.value.title}」。`, time: '1小时前' },
    { id: 'walk', name: '燕园散步者', face: 'walk', text: `${activity.value.place}这边走走就到。`, time: '刚刚' },
  ];
  return [...paint(seed), ...posted.value];
});
const place = computed(() => {
  if (!activity.value) return '';
  const room = activity.value.room && !String(activity.value.place).endsWith(activity.value.room) ? activity.value.room : '';
  return [activity.value.place, activity.value.floor ? `${activity.value.floor}F` : '', room].filter(Boolean).join(' · ');
});

watch(activityId, () => {
  saved.value = false;
  draft.value = '';
  posted.value = [];
  if (scroller.value) scroller.value.scrollTop = 0;
});

function paint(list) {
  let previous = -1;
  return list.map((item, index) => {
    let hash = index * 7;
    for (const char of item.id) hash += char.charCodeAt(0);
    let pick = hash % avatarPencils.length;
    if (pick === previous) pick = (pick + 2) % avatarPencils.length;
    previous = pick;
    return { ...item, pencil: avatarPencils[pick] };
  });
}
function goBack() {
  if (router.options.history.state.back) router.back();
  else router.replace('/map');
}
function publish() {
  const text = draft.value.trim();
  if (!text) return;
  const used = comments.value.at(-1)?.pencil;
  const pencil = avatarPencils.find(item => item !== used) || 'yellow';
  posted.value.push({ id: `me-${posted.value.length}`, name: '我', face: 'me', pencil, text, time: '刚刚' });
  draft.value = '';
  nextTick(() => {
    if (scroller.value) scroller.value.scrollTop = scroller.value.scrollHeight;
  });
}
</script>

<template>
  <section class="detail-page" :style="{ '--kind-ink': kindInk }" :aria-label="activity ? activity.title : '活动详情'">
    <div ref="scroller" class="detail-scroll">
    <template v-if="activity && category">
      <div class="hero">
        <p class="meta">
          <button class="back" type="button" aria-label="返回" @click="goBack">
            <AppIcon name="back" />
          </button>
          <span v-sketch :key="activity.id" class="kind sketch pencil-fill sketch-cast" :data-pencil="category.pencil" :data-cast="category.pencil">
            <i :style="{ background: category.mark }"></i>{{ category.label }}
          </span>
        </p>
        <h1 id="page-title" class="event-title" tabindex="-1">
          <span>{{ activity.title }}</span>
          <svg class="rays" viewBox="0 0 28 22" aria-hidden="true"><path d="M6 16c5-2 9-6 13-12" /><path d="M14 18c3-4 5-8 7-13" /></svg>
        </h1>
      </div>

      <div class="facts">
        <div class="facts-copy">
          <p class="fact">
            <svg viewBox="0 0 32 32" aria-hidden="true"><circle cx="16" cy="16" r="11" fill="currentColor" /><path d="M16 9.5V16l4.5 2.6" fill="none" stroke="#f8f4ea" stroke-width="2.2" stroke-linecap="round" /></svg>
            <span>{{ activity.time }}</span>
          </p>
          <p class="fact">
            <svg viewBox="0 0 32 32" aria-hidden="true"><path fill="currentColor" d="M16 2a10 10 0 0 0-10 11c0 8 10 17 10 17s10-9 10-17A10 10 0 0 0 16 2Z" /><circle cx="16" cy="13" r="3.2" fill="#f8f4ea" /></svg>
            <span>{{ place }}</span>
          </p>
          <p class="fact">
            <svg viewBox="0 0 32 32" aria-hidden="true"><path fill="currentColor" d="M8 4h12l6 6v18H8Z" /><path fill="#f8f4ea" d="M19 4v7h7" /><path fill="#f8f4ea" d="M12 16h9v2h-9zm0 5h7v2h-7z" /></svg>
            <span>来源：{{ activity.source }}</span>
          </p>
        </div>
        <div class="facts-actions">
          <button
            :key="`save-${saved}`"
            v-sketch
            class="action-chip sketch sketch-cast"
            :class="saved ? 'pencil-fill' : 'sketch-white'"
            :data-pencil="saved ? 'yellow' : undefined"
            data-cast="yellow"
            type="button"
            :aria-pressed="saved"
            @click="saved = !saved"
          >{{ saved ? '已收藏' : '加入收藏' }}</button>
          <RouterLink
            v-sketch
            class="action-chip sketch sketch-white sketch-cast"
            data-cast="yellow"
            :to="{ path: '/map', query: { activity: activity.id } }"
          >前往地图</RouterLink>
        </div>
      </div>

      <h3 class="section-title">活动介绍<AppIcon name="spark" /></h3>
      <p class="intro">{{ activity.detail }}</p>

      <div class="talk">
        <div class="talk-head">
          <h3 v-sketch class="talk-tag sketch pencil-fill" data-pencil="yellow">大家都在聊</h3>
          <p>{{ comments.length }} 条评论</p>
        </div>
        <ol>
          <li v-for="item in comments" :key="item.id">
            <span v-sketch class="avatar sketch pencil-fill" :data-pencil="item.pencil"><CommentFace :name="item.face" /></span>
            <div>
              <div class="who"><strong>{{ item.name }}</strong><time>{{ item.time }}</time></div>
              <p>{{ item.text }}</p>
            </div>
          </li>
        </ol>
      </div>
    </template>

    <div v-else class="missing">
      <button class="back" type="button" aria-label="返回" @click="goBack">
        <AppIcon name="back" />
      </button>
      <p>这场活动不在演示名单里。<button type="button" @click="router.replace('/map')">回到活动地图</button></p>
    </div>
    </div>
    <form v-if="activity && category" class="composer" @submit.prevent="publish">
      <label v-sketch class="field sketch sketch-white">
        <svg class="bubble" viewBox="0 0 32 32" aria-hidden="true"><path d="M7 8h14a5 5 0 0 1 5 5v6a5 5 0 0 1-5 5h-6l-6 4v-4H7a5 5 0 0 1-5-5v-6a5 5 0 0 1 5-5Z" /></svg>
        <input v-model="draft" type="text" maxlength="80" placeholder="写下你的想法…" aria-label="写下你的想法" autocomplete="off" />
        <button v-sketch class="send sketch" data-pencil="yellow" type="submit" :disabled="!draft.trim()" aria-label="发送评论">
          <AgentIcon name="send" />
        </button>
      </label>
    </form>
  </section>
</template>

<style scoped>
.detail-page { flex: 1 1 auto; min-height: 0; display: flex; flex-direction: column; overflow: hidden; }
.detail-scroll { flex: 1; min-height: 0; overflow-y: auto; padding-bottom: 8px; scrollbar-width: thin; }
.back { display: grid; place-items: center; width: 36px; height: 36px; flex: none; padding: 6px; border: 0; background: transparent; color: var(--ink); }
.back :deep(.icon) { width: 22px; height: 22px; }
.hero { display: flex; flex-direction: column; }
.meta { display: flex; align-items: center; gap: 6px; margin: 0 0 6px; }
.kind { display: inline-flex; align-items: center; gap: 6px; min-height: 28px; padding: 3px 10px 4px; background: transparent; font-size: 14px; color: var(--ink); }
.kind i { width: 8px; height: 8px; border-radius: 50%; }
.event-title { display: flex; align-items: flex-end; gap: 2px; margin: 0; font-size: 32px; font-weight: 400; line-height: 1.2; letter-spacing: .4px; }
.event-title span { min-width: 0; background: linear-gradient(var(--kind-ink), var(--kind-ink)) left 78% / 100% 9px no-repeat; }
.rays { width: 22px; height: 16px; margin: 0 0 6px; fill: none; stroke: var(--kind-ink); stroke-width: 3.1; stroke-linecap: round; flex: none; }
.facts { display: grid; grid-template-columns: minmax(0, 1fr) 6.6em; gap: 10px 12px; align-items: center; margin-top: 10px; overflow: visible; }
.facts-copy { min-width: 0; }
.fact { display: flex; align-items: center; gap: 10px; margin: 8px 0 0; }
.facts-copy .fact:first-child { margin-top: 0; }
.fact svg { width: 22px; height: 22px; flex: none; color: var(--ink); }
.fact span { font-size: 16px; line-height: 1.4; }
.facts-actions { display: flex; flex-direction: column; gap: 10px; width: 6.6em; overflow: visible; }
.action-chip { display: flex; align-items: center; justify-content: center; width: 100%; min-height: 40px; padding: 6px 8px; border: 0; background: transparent; color: inherit; font-size: 13px; line-height: 1.2; text-align: center; text-decoration: none; white-space: nowrap; }
.section-title { display: inline-flex; align-items: center; gap: 4px; margin: 16px 0 0; font-size: 22px; font-weight: 400; line-height: 1.3; background: linear-gradient(var(--kind-ink), var(--kind-ink)) left 78% / 4.4em 8px no-repeat; }
.section-title :deep(.icon) { width: 14px; height: 14px; color: var(--kind-ink); }
.intro { margin: 8px 0 0; font-size: 15px; line-height: 1.7; }
.talk { margin-top: 16px; }
.talk-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.talk-tag { margin: 0; padding: 5px 14px 6px; background: transparent; font-size: 18px; font-weight: 400; line-height: 1.3; }
.talk-head p { margin: 0; color: var(--muted); font-size: 13px; white-space: nowrap; }
ol { list-style: none; margin: 8px 0 0; padding: 0; }
li { display: grid; grid-template-columns: 44px minmax(0, 1fr); gap: 10px; align-items: center; padding: 8px 0; border-top: 1.5px solid rgb(32 48 75 / 12%); }
li:first-child { border-top: 0; }
.avatar { display: grid; place-items: center; width: 44px; height: 44px; background: transparent; }
.who { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; }
.who strong { font-weight: 400; font-size: 15px; }
.who time { color: var(--muted); font-size: 12px; white-space: nowrap; }
li p { margin: 4px 0 0; font-size: 14px; line-height: 1.55; color: #3e4e68; }
.composer { position: relative; flex: none; margin-top: 0; padding: 8px 0 10px; background: #f8f4ea; }
.field { display: flex; align-items: center; gap: 6px; min-height: 56px; padding: 6px 6px 6px 14px; background: transparent; }
.bubble { width: 22px; height: 22px; flex: none; fill: none; stroke: #8b95a6; stroke-width: 1.8; stroke-linejoin: round; }
.field input { flex: 1; min-width: 0; border: 0; background: transparent; font: inherit; font-size: 15px; color: var(--ink); outline: none; padding: 8px 0; }
.field input::placeholder { color: #8b95a6; }
.send { display: grid; place-items: center; width: 44px; height: 44px; flex: none; padding: 9px; border: 0; background: transparent; color: var(--ink); }
.send :deep(.agent-icon) { width: 22px; height: 22px; }
.send:disabled { opacity: .65; cursor: default; }
.missing { margin: 4px 4px 0; color: var(--muted); font-size: 15px; line-height: 1.7; }
.missing p { margin: 16px 0 0; }
.missing p button { display: inline; margin-left: 6px; padding: 0; border: 0; background: transparent; color: #2f78c4; font: inherit; }
@media (max-width: 359px) {
  .event-title { font-size: 26px; }
  .facts { grid-template-columns: minmax(0, 1fr) 6.2em; gap: 8px; }
  .facts-actions { width: 6.2em; gap: 8px; }
  .action-chip { min-height: 36px; font-size: 12px; }
  .fact span { font-size: 14px; }
  .section-title { font-size: 20px; }
}
</style>
