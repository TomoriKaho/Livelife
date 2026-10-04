<script setup>
import AppIcon from '../../components/AppIcon.vue';

defineProps({
  locationAllowed: { type: Boolean, default: false },
  noticeAllowed: { type: Boolean, default: false },
});
defineEmits(['update:locationAllowed', 'update:noticeAllowed']);
</script>

<template>
  <section class="permission-step" aria-labelledby="onboarding-title">
    <div class="hero-title">
      <AppIcon class="title-spark" name="spark" />
      <h1 id="onboarding-title" tabindex="-1">开启<span class="title-bar">授权</span></h1>
      <AppIcon class="title-spark is-right" name="spark" />
    </div>
    <p class="lede">授权位置并开启通知，我们会为你推荐附近活动</p>

    <article v-sketch class="permit-card sketch sketch-white">
      <span v-sketch class="badge sketch pencil-fill" data-pencil="blue"><AppIcon name="pin" /></span>
      <div>
        <h2>位置权限</h2>
        <p>发现附近活动与教学楼</p>
      </div>
      <button v-sketch class="permit-action sketch sketch-cast" :class="locationAllowed ? 'pencil-fill' : 'sketch-white'" :data-pencil="locationAllowed ? 'yellow' : undefined" type="button" :aria-pressed="locationAllowed" @click="$emit('update:locationAllowed', !locationAllowed)">{{ locationAllowed ? '已允许' : '去设置中打开' }}</button>
    </article>

    <article v-sketch class="permit-card sketch sketch-white">
      <span v-sketch class="badge sketch pencil-fill" data-pencil="pink"><AppIcon name="bell" /></span>
      <div>
        <h2>通知权限</h2>
        <p>不错过收藏活动的开始提醒</p>
      </div>
      <button v-sketch class="permit-action sketch sketch-cast" :class="noticeAllowed ? 'pencil-fill' : 'sketch-white'" :data-pencil="noticeAllowed ? 'yellow' : undefined" type="button" :aria-pressed="noticeAllowed" @click="$emit('update:noticeAllowed', !noticeAllowed)">{{ noticeAllowed ? '已允许' : '去设置中打开' }}</button>
    </article>

    <p class="note">设置可随时更改，数据严格保护在本地设备。</p>
  </section>
</template>

<style scoped>
.permission-step { display: flex; flex-direction: column; align-items: center; }
.hero-title { position: relative; display: flex; align-items: center; justify-content: center; gap: 8px; margin-top: 40px; }
.hero-title h1 { font-size: 28px; text-align: center; }
.title-bar { position: relative; }
.title-bar::after { content: ''; position: absolute; left: 0; right: 0; bottom: -5px; height: 4px; border-radius: 3px; background: #ffdf32; transform: rotate(-2deg); }
.title-spark { width: 16px; height: 16px; color: #ffdf32; }
.is-right { transform: rotate(8deg); }
.title-spark:not(.is-right) { transform: rotate(-8deg); }
.lede { margin: 8px 0 48px; width: 100%; text-align: center; color: var(--muted); font-size: 13px; line-height: 1.55; }
.permit-card { width: 100%; display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: 10px; align-items: center; margin-bottom: 12px; padding: 12px; background: transparent; text-align: left; }
.badge { width: 44px; height: 44px; display: grid; place-items: center; background: transparent; color: var(--ink); }
.badge :deep(.icon) { width: 22px; height: 22px; }
.permit-card h2 { margin: 0; font-size: 16px; font-weight: 400; line-height: 1.3; }
.permit-card p { margin: 2px 0 0; font-size: 13px; color: var(--muted); line-height: 1.4; }
.permit-action { height: 48px; min-height: 48px; padding: 8px 14px; background: transparent; border: 0; font-size: 14px; white-space: nowrap; }
.note { width: 100%; margin: 8px 0 0; padding: 0; text-align: center; color: var(--muted); font-size: 12px; line-height: 1.5; }
@media (max-width: 359px) {
  .hero-title h1 { font-size: 24px; }
  .permit-card { gap: 8px; padding: 10px; }
}
</style>
