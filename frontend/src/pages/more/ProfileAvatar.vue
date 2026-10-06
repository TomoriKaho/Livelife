<script setup>
import UserPlaneAvatar from '../agent/UserPlaneAvatar.vue';
defineProps({ kind: { type: String, default: 'student' } });
</script>
<template>
  <div v-sketch class="profile-avatar sketch pencil-fill" :data-pencil="kind === 'leaf' ? 'mint' : 'yellow'" aria-hidden="true">
    <div v-if="kind === 'student'" class="avatar-art plane-art"><UserPlaneAvatar /></div>
    <svg v-else-if="kind === 'star'" class="avatar-art" viewBox="0 0 80 80"><path class="face" d="M40 15 48 31 66 34 53 47 55 65 40 56 24 65 27 47 14 34 32 31Z" /><path d="M32 39 32.5 39 M48 39 48.5 39 M35 48 Q40 52 45 48" /></svg>
    <svg v-else class="avatar-art" viewBox="0 0 80 80"><path class="leaf" d="M21 55 Q14 22 59 16 Q67 55 33 59Z" /><path d="M23 66 Q29 45 49 28 M32 48 26 35 M39 39 54 39" /></svg>
  </div>
</template>
<style scoped>
.profile-avatar { display: grid; place-items: center; width: 82px; height: 82px; flex: none; background: transparent; }
.avatar-art { width: 73px; height: 73px; fill: none; stroke: var(--ink); stroke-width: 1.65; stroke-linecap: round; stroke-linejoin: round; }
.plane-art { display: grid; place-items: center; stroke: none; }
.plane-art :deep(.user-plane) { width: 78%; height: 78%; }
.face { fill: #fbf8ef; fill-opacity: .86; }.leaf { fill: #fbf8ef; fill-opacity: .72; }
</style>
