<script setup>
import { RouterLink } from 'vue-router';
import AppIcon from '../../../components/AppIcon.vue';
defineProps({ active: { type: String, default: '' } });
const items = [
  { key: 'map', label: '活动地图', icon: 'map' },
  { key: 'calendar', label: '活动日历', icon: 'calendar' },
  { key: 'interests', label: '兴趣广场', icon: 'star' },
  { key: 'agent', label: '智能助手', icon: 'agent' },
  { key: 'more', label: '我的', icon: 'user' },
];
</script>

<template>
  <nav v-sketch class="bottom-nav pencil-fill" data-pencil="yellow" aria-label="主导航">
    <RouterLink v-for="item in items" :key="item.key" v-sketch class="nav-item" :to="`/${item.key}`" :data-nav="item.key"
      :aria-current="active === item.key ? 'page' : undefined" :data-pencil="active === item.key ? 'blue' : undefined">
      <AppIcon :name="item.icon" /><span>{{ item.label }}</span>
    </RouterLink>
  </nav>
</template>
