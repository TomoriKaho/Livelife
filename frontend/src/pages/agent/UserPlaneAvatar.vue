<script setup>
import { useId } from 'vue';
const pencil = 'user-plane-' + useId().replace(/:/g, '');
const silhouette = 'M3 26 57 13 47 30 52 43 42 38 34 53Z';
const fold = 'M3 26 47 30 52 43 43 36Z';
</script>

<template>
  <svg class="user-plane" viewBox="0 0 60 60" focusable="false">
    <defs>
      <pattern :id="pencil" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(-30)">
        <path d="M0 1h5" stroke="#fff" stroke-width="1.4" opacity=".3" />
      </pattern>
      <pattern :id="pencil + '-fold'" width="4" height="4" patternUnits="userSpaceOnUse">
        <path d="M1 0v4" stroke="#123c76" stroke-width="1.1" opacity=".65" />
      </pattern>
    </defs>
    <!-- Reference silhouette, turned left: broad wings, a narrow crease, and a hanging fold. -->
    <path :d="silhouette" fill="#9ac8f2" />
    <path d="M3 26 57 13 47 30Z" fill="#b7dcf9" />
    <path d="M3 26 43 36 34 53Z" fill="#9ac8f2" />
    <path d="m43 36 9 7-10-5Z" fill="#73ade0" />
    <path :d="silhouette" :fill="'url(#' + pencil + ')'" />
    <path :d="fold" :fill="'url(#' + pencil + '-fold)'" />
    <g fill="none" stroke="#123c76" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round">
      <path :d="silhouette" />
      <path d="m3 26 44 4 5 13 M3 26l40 10 9 7 M43 36l-1 2" />
    </g>
  </svg>
</template>

<style scoped>
.user-plane { display: block; width: 100%; height: 100%; }
</style>
