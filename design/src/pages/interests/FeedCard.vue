<script setup>
import FeedArt from './FeedArt.vue';
import InterestIcon from './InterestIcon.vue';
import PlatformMark from './PlatformMark.vue';
import { platformOf } from './demo.js';

defineProps({
  item: { type: Object, required: true },
  saved: Boolean,
});
defineEmits(['open', 'save']);
</script>

<template>
  <article v-sketch class="feed-card sketch sketch-white sketch-cast" :data-cast="platformOf(item.platform)?.pencil || 'blue'">
    <button class="card-body" type="button" :aria-label="`查看 ${item.title}`" @click="$emit('open', item)">
      <span class="art-wrap" aria-hidden="true"><FeedArt :name="item.art" /></span>
      <span class="card-copy">
        <span class="platform">
          <PlatformMark :name="platformOf(item.platform)?.mark || item.platform" />
          {{ platformOf(item.platform)?.label || item.platform }}
        </span>
        <strong>{{ item.title }}</strong>
        <span class="meta"><InterestIcon name="clock" />{{ item.meta }}</span>
        <span class="reason"><InterestIcon name="spark" />{{ item.reason }} <em>{{ item.highlight }}</em>{{ item.suffix ? ` ${item.suffix}` : '' }}</span>
      </span>
    </button>
    <button
      class="save"
      type="button"
      :aria-pressed="saved"
      :aria-label="saved ? `取消收藏：${item.title}` : `收藏：${item.title}`"
      @click="$emit('save', item)"
    >
      <span v-if="saved" v-sketch class="save-wash sketch pencil-fill sketch-fill-only" data-pencil="yellow" aria-hidden="true"></span>
      <InterestIcon class="save-icon" :class="{ on: saved }" name="bookmark" />
    </button>
  </article>
</template>

<style scoped>
.feed-card { position: relative; overflow: visible; background: transparent; }
.card-body {
  display: grid;
  grid-template-columns: 76px minmax(0, 1fr);
  gap: 10px;
  width: 100%;
  min-height: 108px;
  padding: 12px 40px 12px 12px;
  border: 0;
  background: transparent;
  color: inherit;
  text-align: left;
}
.art-wrap { display: grid; place-items: center; width: 76px; height: 76px; align-self: center; }
.card-copy { display: flex; flex-direction: column; min-width: 0; gap: 4px; padding-top: 1px; }
.platform { display: inline-flex; align-items: center; gap: 5px; color: var(--muted); font-size: 12px; line-height: 1.2; }
.card-copy strong { font-size: 15px; font-weight: 400; line-height: 1.4; overflow-wrap: anywhere; }
.meta, .reason { display: inline-flex; align-items: center; gap: 5px; color: var(--muted); font-size: 11px; line-height: 1.4; }
.reason em { font-style: normal; color: #3d86c8; }
.save { position: absolute; top: 6px; right: 4px; display: grid; place-items: center; width: 40px; height: 40px; border: 0; background: transparent; color: var(--ink); }
.save-wash { position: absolute; inset: 6px; background: transparent; }
.save-icon { position: relative; width: 17px; height: 17px; }
.save-icon.on { color: #c9a227; }
@media (max-width: 359px) {
  .card-body { grid-template-columns: 64px minmax(0, 1fr); padding: 10px 36px 10px 10px; gap: 8px; }
  .art-wrap { width: 64px; height: 64px; }
  .card-copy strong { font-size: 14px; }
}
</style>
