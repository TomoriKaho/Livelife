<script setup lang="ts">
import { computed, watch } from 'vue';
import { RouterLink } from 'vue-router';
import { authState, readAuthToken } from '../api/auth';
import { isInformationId } from '../api/favorites';
import { favorites, checkFavorites } from '../state/favorites';

const props = defineProps<{ id: string; platform?: string }>();
const state = favorites.state;
const loggedIn = computed(() => { void authState.revision; return Boolean(readAuthToken()); });
const eligible = computed(() => isInformationId(props.id) && props.platform !== 'demo');
watch(() => [props.id, props.platform, authState.revision], () => {
  if (eligible.value && loggedIn.value) checkFavorites([props.id]);
}, { immediate: true });
async function toggle() {
  if (state.saved[props.id] === undefined || state.errors[props.id]) { checkFavorites([props.id]); return; }
  await favorites.set(props.id, !state.saved[props.id]);
}
</script>
<template>
  <div class="favorite-control">
    <small v-if="!eligible">演示活动不支持账号收藏</small>
    <RouterLink v-else-if="!loggedIn" class="favorite-login" to="/login">登录后收藏</RouterLink>
    <template v-else>
      <button v-sketch class="sketch favorite-toggle" :data-pencil="state.saved[id] ? 'yellow' : undefined" type="button"
        :disabled="state.pending[id] || state.checking[id]" :aria-pressed="state.saved[id] === true" :data-favorite-id="id" @click="toggle">
        {{ state.pending[id] ? '正在保存…' : state.checking[id] ? '读取收藏…' : state.errors[id] ? '重试收藏状态' : state.saved[id] === undefined ? '读取收藏状态' : state.saved[id] ? '取消收藏' : '收藏活动' }}
      </button>
      <small v-if="state.errors[id]" role="alert">{{ state.errors[id] }}</small>
    </template>
  </div>
</template>
<style scoped>
.favorite-control { min-width: 0; max-width: 100%; margin: 8px 0; font-size: 12px; }.favorite-toggle,.favorite-login { display: inline-flex; align-items: center; justify-content: center; max-width: 100%; min-height: 44px; padding: 8px 14px; color: var(--ink); background: transparent; text-decoration: none; white-space: normal; overflow-wrap: anywhere; }.favorite-control small { display: block; margin-top: 6px; color: var(--muted); line-height: 1.6; overflow-wrap: anywhere; }button:disabled { opacity: .6; }
</style>
