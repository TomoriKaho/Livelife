<script setup>
defineProps({ name: { type: String, required: true } });
</script>

<template>
  <svg class="mark" viewBox="0 0 28 28" aria-hidden="true">
    <g v-if="name === 'wechat'">
      <path d="M6.5 9.2q0-4.4 7.2-4.4t7.2 4.4-7.2 4.8l-2.4 1.8.6-2.1Q6.5 13.2 6.5 9.2Z" fill="#88cbb2" stroke="#20304b" stroke-width="1.5" />
      <path d="M8.2 17.4q1.2 3.6 6.4 3.6 5.4 0 6.6-3.4l2.2 1.6-.4-1.8q2.4-.8 2.4-3.8 0-3.4-5.4-3.4" fill="#d0f1de" stroke="#20304b" stroke-width="1.5" />
      <circle cx="11.2" cy="8.8" r="1" fill="#20304b" />
      <circle cx="16.2" cy="8.8" r="1" fill="#20304b" />
    </g>
    <g v-else-if="name === 'zhihu'">
      <circle cx="14" cy="14" r="10.2" fill="#78b8ed" stroke="#20304b" stroke-width="1.6" />
      <path d="M11 9.2h7.4M14.6 9.4v10.2M11.2 19.6h6.8" fill="none" stroke="#20304b" stroke-width="1.7" stroke-linecap="round" />
      <path d="M10.4 13.6h4.2l-3.4 4" fill="none" stroke="#fffdf8" stroke-width="1.5" stroke-linecap="round" />
    </g>
    <g v-else-if="name === 'xhs'">
      <rect x="6.2" y="6.4" width="15.6" height="16.2" rx="3.4" fill="#f7b4ae" stroke="#20304b" stroke-width="1.6" />
      <path d="M10 11.2h8.2M10 15h8.2M10 18.6h5.4" fill="none" stroke="#20304b" stroke-width="1.5" stroke-linecap="round" />
      <circle cx="19.2" cy="8.8" r="1.5" fill="#ffdf32" stroke="#20304b" stroke-width="1" />
    </g>
    <g v-else-if="name === 'official'">
      <path d="M7 22V11l7-5 7 5v11Z" fill="#c4afea" stroke="#20304b" stroke-width="1.6" />
      <path d="M12 22v-6h4v6" fill="#fffdf8" stroke="#20304b" stroke-width="1.4" />
      <path d="M10 13h2M16 13h2M10 16h2M16 16h2" fill="none" stroke="#20304b" stroke-width="1.3" stroke-linecap="round" />
    </g>
    <g v-else>
      <circle cx="10.2" cy="11.2" r="3.2" fill="#5ea7e5" stroke="#20304b" stroke-width="1.3" />
      <circle cx="17.8" cy="11.2" r="3.2" fill="#e99796" stroke="#20304b" stroke-width="1.3" />
      <circle cx="10.8" cy="17.6" r="3.2" fill="#ffd600" stroke="#20304b" stroke-width="1.3" />
      <circle cx="18.2" cy="17.6" r="3.2" fill="#88cbb2" stroke="#20304b" stroke-width="1.3" />
    </g>
  </svg>
</template>

<style scoped>
.mark { width: 20px; height: 20px; flex: none; overflow: visible; }
</style>
