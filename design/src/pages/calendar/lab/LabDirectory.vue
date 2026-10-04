<script setup>
import { ref } from 'vue';
import { RouterLink } from 'vue-router';
import { pages } from '../../../router/index.js';
import AppIcon from '../../../components/AppIcon.vue';
defineProps({ active: { type: String, default: '' } });
const emit = defineEmits(['select']);
const dialog = ref(null);
function close() { dialog.value?.close(); }
function select() { close(); emit('select'); }
function closeOnBackdrop(event) {
  const bounds = dialog.value.getBoundingClientRect();
  if (event.target === dialog.value && (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom)) close();
}
defineExpose({ open: () => { if (!dialog.value.open) dialog.value.showModal(); } });
</script>

<template>
  <dialog id="calendar-lab-directory" ref="dialog" v-sketch class="page-directory sketch" aria-labelledby="calendar-lab-directory-title" @click="closeOnBackdrop">
    <div class="directory-header">
      <div><p class="eyebrow">OUR LITTLE SKETCHBOOK</p><h2 id="calendar-lab-directory-title">页面目录</h2></div>
      <button id="calendar-lab-close-directory" v-sketch class="icon-button" type="button" aria-label="关闭页面目录" @click="close"><AppIcon name="close" /></button>
    </div>
    <p class="directory-description">先搭好框架，再一页页填上生活。</p>
    <nav class="directory-links" aria-label="全部设计页面">
      <RouterLink v-for="page in pages" :key="page.key" v-sketch class="directory-link" :to="`/${page.key}`" :data-route="page.key"
        :aria-current="active === page.key ? 'page' : undefined" :data-pencil="active === page.key ? 'blue' : undefined" @click="select">
        <span class="route-code">{{ page.id }}</span><span>{{ page.placeholder }}</span><AppIcon name="chevron" />
      </RouterLink>
    </nav>
    <p class="directory-note">D-01 含登录与引导，其余页面仍为内容占位</p>
  </dialog>
</template>
