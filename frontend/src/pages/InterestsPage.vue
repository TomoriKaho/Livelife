<script>
export const pageMeta = {
  key: 'interests',
  id: 'D-05',
  title: '兴趣广场',
  placeholder: '兴趣画像、标签与跨平台内容流',
  label: 'INTERESTS',
  eyebrow: '',
  icon: 'star',
  accent: 'pink',
  nav: 'interests',
  back: false,
  heading: false,
  footer: false,
};
</script>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref } from 'vue';
import FeedCard from './interests/FeedCard.vue';
import InterestIcon from './interests/InterestIcon.vue';
import {
  customPencils,
  feedItems,
  initialTagIds,
  platforms,
  portraitText,
  tags,
} from './interests/demo.js';

const query = ref('');
const editing = ref(false);
const showingSaved = ref(false);
const filterOpen = ref(false);
const notice = ref('');
const filterWrap = ref(null);
const title = ref(null);
const customInput = ref(null);
const customLabel = ref('');
const customTags = ref([]);
const picked = ref([...initialTagIds]);
const draft = ref([...initialTagIds]);
const activeTags = ref([...initialTagIds]);
const saved = ref(new Set());
const hiddenPlatforms = ref(new Set());
const removedIds = ref(new Set());
const draftRemoved = ref(new Set());
let noticeTimer;
let customSeq = 0;

const catalog = computed(() => [...tags, ...customTags.value].filter((item) => !removedIds.value.has(item.id)));
const editorCatalog = computed(() => catalog.value.filter((item) => !draftRemoved.value.has(item.id)));
const pickedTags = computed(() => picked.value.map((id) => catalog.value.find((item) => item.id === id)).filter(Boolean));
const allTagsActive = computed(() => picked.value.length > 0 && picked.value.every((id) => activeTags.value.includes(id)) && activeTags.value.length === picked.value.length);
const filtered = computed(() => {
  const text = query.value.trim().toLowerCase();
  return feedItems.filter((item) => {
    if (hiddenPlatforms.value.has(item.platform)) return false;
    if (!activeTags.value.includes(item.tag)) return false;
    if (!text) return true;
    const hay = [item.title, item.meta, item.highlight, item.reason, item.suffix, item.platform]
      .filter(Boolean)
      .join(' ')
      .toLowerCase();
    const tagLabel = catalog.value.find((tag) => tag.id === item.tag)?.label.toLowerCase() || '';
    return hay.includes(text) || tagLabel.includes(text);
  });
});
const updateLabel = computed(() => {
  if (query.value.trim() || !allTagsActive.value || hiddenPlatforms.value.size) return `找到 ${filtered.value.length} 条`;
  return `今日更新 ${feedItems.length} 条`;
});
const savedItems = computed(() => [...saved.value].reverse().map((id) => feedItems.find((item) => item.id === id)).filter(Boolean));

function notify(text) {
  clearTimeout(noticeTimer);
  notice.value = text;
  noticeTimer = setTimeout(() => { notice.value = ''; }, 2400);
}
function toggleTag(id) {
  activeTags.value = activeTags.value.includes(id)
    ? activeTags.value.filter((value) => value !== id)
    : [...activeTags.value, id];
}
function toggleSave(item) {
  const next = new Set(saved.value);
  if (next.has(item.id)) {
    next.delete(item.id);
    notify(`已取消收藏「${item.title}」`);
  } else {
    next.add(item.id);
    notify(`已收藏「${item.title}」`);
  }
  saved.value = next;
}
function openItem(item) {
  notify('外链阅读将在后续开放');
}
function openSaved() {
  showingSaved.value = true;
  editing.value = false;
  filterOpen.value = false;
  nextTick(() => title.value?.focus({ preventScroll: true }));
}
function closeSaved() {
  showingSaved.value = false;
  nextTick(() => title.value?.focus({ preventScroll: true }));
}
function openEditor() {
  draft.value = [...picked.value];
  draftRemoved.value = new Set();
  customLabel.value = '';
  editing.value = true;
  showingSaved.value = false;
  filterOpen.value = false;
  nextTick(() => title.value?.focus({ preventScroll: true }));
}
function closeEditor() {
  editing.value = false;
  draftRemoved.value = new Set();
  customLabel.value = '';
  nextTick(() => title.value?.focus({ preventScroll: true }));
}
function toggleDraft(id) {
  draft.value = draft.value.includes(id) ? draft.value.filter((value) => value !== id) : [...draft.value, id];
}
function removeTag(item) {
  draftRemoved.value = new Set([...draftRemoved.value, item.id]);
  draft.value = draft.value.filter((id) => id !== item.id);
  notify(`已删除「${item.label}」`);
}
function addCustomTag() {
  const label = customLabel.value.trim().replace(/\s+/g, ' ');
  if (!label) return;
  const existed = catalog.value.find((item) => item.label.toLowerCase() === label.toLowerCase());
  if (existed) {
    if (!draft.value.includes(existed.id)) draft.value = [...draft.value, existed.id];
    customLabel.value = '';
    notify(`已选中「${existed.label}」`);
    return;
  }
  const item = {
    id: `custom-${++customSeq}`,
    label,
    group: 'custom',
    pencil: customPencils[(customTags.value.length + customSeq) % customPencils.length],
  };
  customTags.value = [...customTags.value, item];
  draft.value = [...draft.value, item.id];
  customLabel.value = '';
  nextTick(() => customInput.value?.focus());
}
function savePortrait() {
  const previous = new Set(picked.value);
  const dropped = draftRemoved.value;
  removedIds.value = new Set([...removedIds.value, ...dropped]);
  customTags.value = customTags.value.filter((item) => !dropped.has(item.id));
  picked.value = draft.value.filter((id) => !dropped.has(id));
  activeTags.value = [
    ...activeTags.value.filter((id) => picked.value.includes(id)),
    ...picked.value.filter((id) => !previous.has(id)),
  ];
  draftRemoved.value = new Set();
  editing.value = false;
  customLabel.value = '';
  notify('兴趣标签已更新');
  nextTick(() => title.value?.focus({ preventScroll: true }));
}
function togglePlatform(id) {
  const next = new Set(hiddenPlatforms.value);
  if (next.has(id)) next.delete(id);
  else next.add(id);
  if (next.size === platforms.length) next.delete(id);
  hiddenPlatforms.value = next;
}
function onPointerDown(event) {
  if (filterOpen.value && filterWrap.value && !filterWrap.value.contains(event.target)) filterOpen.value = false;
}
if (typeof document !== 'undefined') document.addEventListener('pointerdown', onPointerDown);
onBeforeUnmount(() => {
  clearTimeout(noticeTimer);
  document.removeEventListener('pointerdown', onPointerDown);
});
</script>

<template>
  <section class="interests-page" aria-labelledby="page-title">
    <template v-if="showingSaved">
      <header class="editor-heading">
        <button v-sketch class="back sketch" type="button" @click="closeSaved">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14 5 7 12l7 7" /></svg>
          返回
        </button>
        <h1 id="page-title" ref="title" tabindex="-1">我的收藏</h1>
      </header>
      <p class="editor-lede">{{ savedItems.length ? `已收下 ${savedItems.length} 篇` : '还没有收下文章。' }}</p>
      <div v-if="savedItems.length" class="feed-list">
        <FeedCard
          v-for="item in savedItems"
          :key="item.id"
          :item="item"
          :saved="true"
          @open="openItem"
          @save="toggleSave"
        />
      </div>
      <p v-else class="empty">点内容卡右上角的书签，喜欢的文章会留在这里。</p>
    </template>

    <template v-else-if="!editing">
      <div class="toolbar">
        <div class="title-block">
          <h1 id="page-title" ref="title" tabindex="-1">兴趣广场</h1>
          <p class="lede">从全网发现你真正感兴趣的内容</p>
        </div>
        <button v-sketch class="saved-entry sketch sketch-white sketch-cast" data-cast="yellow" type="button" @click="openSaved">
          <InterestIcon name="bookmark" />
          我的收藏
          <small v-if="saved.size">{{ saved.size }}</small>
        </button>
      </div>

      <div ref="filterWrap" class="search-wrap">
        <label v-sketch class="search-bar sketch sketch-white">
          <InterestIcon name="search" />
          <input v-model="query" type="search" placeholder="搜索内容、话题或平台" aria-label="搜索内容、话题或平台" autocomplete="off" />
          <button
            class="filter-button"
            type="button"
            aria-label="按平台筛选"
            :aria-expanded="filterOpen"
            aria-controls="platform-filter"
            @click="filterOpen = !filterOpen"
          >
            <InterestIcon name="sliders" />
          </button>
        </label>
        <div v-if="filterOpen" id="platform-filter" v-sketch class="filter-sheet sketch sketch-white" role="group" aria-label="选择平台">
          <p>看看哪些平台</p>
          <div class="filter-chips">
            <button
              v-for="item in platforms"
              :key="`${item.id}-${!hiddenPlatforms.has(item.id)}`"
              v-sketch
              class="filter-chip sketch sketch-cast"
              :class="hiddenPlatforms.has(item.id) ? 'sketch-white' : 'pencil-fill'"
              :data-pencil="hiddenPlatforms.has(item.id) ? undefined : item.pencil"
              :data-cast="item.pencil"
              type="button"
              :aria-pressed="!hiddenPlatforms.has(item.id)"
              @click="togglePlatform(item.id)"
            >{{ item.label }}</button>
          </div>
        </div>
      </div>

      <section class="tag-block" aria-labelledby="tag-title">
        <h2 id="tag-title">推荐标签</h2>
        <div class="tag-row" role="group" aria-label="用兴趣标签筛选内容">
          <button
            v-for="item in pickedTags"
            :key="`${item.id}-${activeTags.includes(item.id)}`"
            v-sketch
            class="tag sketch sketch-cast"
            :class="activeTags.includes(item.id) ? 'pencil-fill' : 'sketch-white'"
            :data-pencil="activeTags.includes(item.id) ? item.pencil : undefined"
            :data-cast="item.pencil"
            type="button"
            :aria-pressed="activeTags.includes(item.id)"
            @click="toggleTag(item.id)"
          >{{ item.label }}</button>
          <button v-sketch class="tag add-tag sketch" type="button" @click="openEditor">
            <InterestIcon name="plus" />添加兴趣
          </button>
        </div>
      </section>

      <section class="feed" aria-labelledby="feed-title">
        <header class="feed-head">
          <h2 id="feed-title">为你搜集</h2>
          <p>{{ updateLabel }}</p>
        </header>
        <div v-if="filtered.length" class="feed-list">
          <FeedCard
            v-for="item in filtered"
            :key="item.id"
            :item="item"
            :saved="saved.has(item.id)"
            @open="openItem"
            @save="toggleSave"
          />
        </div>
        <p v-else class="empty">这组兴趣里暂时没有新内容，换个标签或平台再看看。</p>
      </section>
    </template>

    <template v-else>
      <header class="editor-heading">
        <button v-sketch class="back sketch" type="button" @click="closeEditor">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14 5 7 12l7 7" /></svg>
          返回
        </button>
        <h1 id="page-title" ref="title" tabindex="-1">添加兴趣</h1>
      </header>
      <p class="editor-lede">圈一圈想看的事，也可以自己写一个标签。</p>
      <p class="draft-summary">{{ portraitText(draft, customTags) }}</p>
      <div class="editor-grid" role="group" aria-label="选择兴趣标签">
        <button
          v-for="item in editorCatalog"
          :key="item.id"
          v-sketch
          class="editor-tag sketch sketch-cast"
          :class="draft.includes(item.id) ? 'pencil-fill' : 'sketch-white'"
          :data-pencil="draft.includes(item.id) ? item.pencil : undefined"
          :data-cast="item.pencil"
          type="button"
          :aria-pressed="draft.includes(item.id)"
          @click="toggleDraft(item.id)"
        >
          {{ item.label }}
          <span class="remove-tag" role="button" :aria-label="`删除 ${item.label}`" @click.stop="removeTag(item)">
            <InterestIcon name="trash" />
          </span>
        </button>
      </div>
      <label class="custom-field">
        <span>自己写一个标签</span>
        <div class="custom-row">
          <div v-sketch class="field-outline sketch">
            <input
              ref="customInput"
              v-model="customLabel"
              maxlength="12"
              aria-label="自定义兴趣标签"
              placeholder="例如：摄影、话剧"
              autocomplete="off"
              @keydown.enter.prevent="addCustomTag"
            />
          </div>
          <button v-sketch class="add-custom sketch" data-pencil="blue" type="button" :disabled="!customLabel.trim()" @click="addCustomTag">
            加上
          </button>
        </div>
      </label>
      <p class="picked-count">已选 {{ draft.length }} 项</p>
      <button v-sketch class="save-portrait sketch" data-pencil="yellow" type="button" @click="savePortrait">
        保存兴趣 <InterestIcon name="check" />
      </button>
    </template>

    <Teleport to=".phone-shell" defer>
      <Transition name="interest-toast">
        <p v-if="notice" v-sketch class="interest-notice sketch" data-pencil="yellow" role="status">{{ notice }}</p>
      </Transition>
    </Teleport>
  </section>
</template>

<style scoped>
.interests-page { display: flex; flex-direction: column; flex-shrink: 0; padding-bottom: 16px; }
.toolbar { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; margin: 2px 0 10px; }
.title-block { display: flex; align-items: baseline; flex-wrap: wrap; gap: 6px 10px; min-width: 0; flex: 1; }
.interests-page h1 { position: relative; margin: 0; padding-bottom: 5px; font-size: 26px; line-height: 1.15; letter-spacing: .3px; }
.interests-page h1::after { content: ''; position: absolute; left: 1px; right: 4px; bottom: 0; height: 4px; border-radius: 5px; background: #ffdf32; transform: rotate(-2deg); }
.lede { margin: 0; color: var(--muted); font-size: 13px; line-height: 1.35; min-width: 8em; }
.saved-entry { display: inline-flex; align-items: center; gap: 5px; flex: none; min-height: 36px; margin-top: 2px; padding: 6px 10px; border: 0; background: transparent; font-size: 13px; }
.saved-entry .interest-icon { width: 14px; height: 14px; }
.saved-entry small { font-size: 11px; color: var(--muted); }
.search-wrap { position: relative; margin-bottom: 12px; }
.search-bar { display: flex; align-items: center; gap: 8px; min-height: 44px; padding: 5px 8px 5px 14px; background: transparent; }
.search-bar input { width: 100%; min-width: 0; padding: 6px 0; border: 0; background: transparent; color: var(--ink); font: inherit; font-size: 14px; outline: none; }
.search-bar input::placeholder { color: var(--muted); }
.search-bar:focus-within { outline: 2px solid #456e9977; outline-offset: 2px; border-radius: 14px; }
.filter-button { display: grid; place-items: center; width: 40px; height: 40px; border: 0; background: transparent; color: var(--ink); }
.filter-sheet { position: absolute; z-index: 4; top: calc(100% + 6px); right: 0; left: 0; padding: 12px 14px 14px; background: transparent; }
.filter-sheet p { margin: 0 2px 10px; font-size: 13px; color: var(--muted); }
.filter-chips { display: flex; flex-wrap: wrap; gap: 8px; }
.filter-chip { min-height: 36px; padding: 6px 12px; border: 0; background: transparent; font-size: 13px; }
.tag-block h2, .feed-head h2 { margin: 0; font-size: 16px; font-weight: 400; }
.tag-block { margin-bottom: 14px; }
.tag-row { display: flex; flex-wrap: wrap; gap: 7px; margin-top: 8px; }
.tag { min-height: 36px; padding: 6px 12px; border: 0; background: transparent; font-size: 13px; }
.add-tag { display: inline-flex; align-items: center; gap: 4px; }
.feed-head { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; margin-bottom: 10px; }
.feed-head p { margin: 0; color: var(--muted); font-size: 12px; }
.feed-list { display: flex; flex-direction: column; gap: 12px; overflow: visible; }
.empty { margin: 18px 2px 0; color: var(--muted); font-size: 13px; line-height: 1.7; }
.editor-heading { display: flex; align-items: center; gap: 10px; min-height: 44px; margin: 0 0 14px; }
.editor-heading h1 { font-size: 23px; }
.back { display: inline-flex; align-items: center; gap: 2px; flex: none; min-height: 36px; padding: 4px 10px 4px 6px; border: 0; background: transparent; color: var(--ink); font-size: 15px; }
.back svg { width: 16px; height: 16px; fill: none; stroke: currentColor; stroke-width: 2.4; stroke-linecap: round; stroke-linejoin: round; }
.editor-lede { margin: 0 2px 12px; color: var(--muted); font-size: 14px; line-height: 1.8; }
.draft-summary { margin: 0 2px 18px; font-size: 15px; line-height: 1.7; }
.editor-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.editor-tag { position: relative; display: flex; align-items: center; justify-content: center; gap: 6px; min-height: 52px; padding: 10px 28px 10px 8px; border: 0; background: transparent; font-size: 14px; }
.editor-tag .interest-icon { width: 15px; height: 15px; }
.remove-tag { position: absolute; right: 6px; display: grid; place-items: center; width: 22px; height: 22px; color: var(--muted); }
.remove-tag .interest-icon { width: 14px; height: 14px; }
.custom-field { display: block; margin: 18px 0 4px; }
.custom-field > span { display: block; margin: 0 2px 8px; font-size: 13px; }
.custom-row { display: grid; grid-template-columns: minmax(0, 1fr) 72px; gap: 8px; align-items: center; }
.field-outline { padding: 10px 12px; background: transparent; }
.field-outline input { display: block; width: 100%; min-height: 28px; padding: 3px 0; margin: 0; border: 0; background: transparent; color: var(--ink); font: inherit; font-size: 16px; outline: none; }
.field-outline input::placeholder { color: var(--muted); }
.field-outline:focus-within { outline: 2px solid #456e9977; outline-offset: -2px; border-radius: 14px; }
.add-custom { min-height: 48px; padding: 8px 6px; border: 0; background: transparent; font-size: 14px; }
.add-custom:disabled { opacity: .45; cursor: default; }
.picked-count { margin: 16px 2px 8px; color: var(--muted); font-size: 13px; }
.save-portrait { display: flex; align-items: center; justify-content: center; gap: 10px; width: 100%; min-height: 52px; margin-top: 8px; padding: 12px; background: transparent; font-size: 16px; }
.save-portrait .interest-icon { width: 18px; height: 18px; }
.interest-notice {
  position: absolute;
  z-index: 75;
  bottom: calc(105px + env(safe-area-inset-bottom, 0px));
  left: 50%;
  transform: translateX(-50%);
  width: max-content;
  max-width: calc(100% - 40px);
  margin: 0;
  padding: 13px 18px;
  font-size: 13px;
  text-align: center;
  background: transparent;
}
.interest-toast-enter-active, .interest-toast-leave-active { transition: opacity .2s ease; }
.interest-toast-enter-from, .interest-toast-leave-to { opacity: 0; }
@media (max-width: 359px) {
  .interests-page h1 { font-size: 22px; }
  .lede { font-size: 12px; min-width: 7em; }
  .saved-entry { font-size: 12px; padding: 6px 8px; }
  .tag { font-size: 12px; padding: 6px 10px; }
  .editor-tag { font-size: 13px; }
  .custom-row { grid-template-columns: minmax(0, 1fr) 64px; }
}
@media (prefers-reduced-motion: reduce) {
  .interest-toast-enter-active, .interest-toast-leave-active { transition: none; }
}
</style>
