<script setup>
defineProps({ name: { type: String, required: true } });
</script>

<template>
  <svg class="art" viewBox="0 0 88 88" aria-hidden="true">
    <g v-if="name === 'robot'">
      <path d="M70 12c1.6 3.2 2.4 4 5.6 5.6-3.2 1.6-4 2.4-5.6 5.6-1.6-3.2-2.4-4-5.6-5.6 3.2-1.6 4-2.4 5.6-5.6Z" fill="#ffd600" />
      <circle cx="16" cy="18" r="2.2" fill="#78b8ed" />
      <circle cx="72" cy="30" r="2" fill="#ab94de" />
      <circle cx="20" cy="58" r="1.8" fill="#f7b4ae" />
      <path d="M18 20 28 28M70 32 62 36M22 56l10-6" fill="none" stroke="#78b8ed" stroke-width="1.3" />
      <rect x="26" y="22" width="36" height="34" rx="11" fill="#fffdf8" stroke="#20304b" stroke-width="2.1" />
      <circle cx="37" cy="36" r="4.4" fill="#78b8ed" stroke="#20304b" stroke-width="1.5" />
      <circle cx="51" cy="36" r="4.4" fill="#78b8ed" stroke="#20304b" stroke-width="1.5" />
      <path d="M36 47h16" fill="none" stroke="#20304b" stroke-width="1.9" stroke-linecap="round" />
      <path d="M44 22v-8M18 38h8M62 38h8M33 62v10M55 62v10M29 74h10M49 74h10" fill="none" stroke="#20304b" stroke-width="1.8" stroke-linecap="round" />
    </g>
    <g v-else-if="name === 'idea'">
      <path d="M70 16c1.6 3 2.2 3.8 5.2 5.2-3 1.4-3.6 2.2-5.2 5.2-1.6-3-2.2-3.8-5.2-5.2 3-1.4 3.6-2.2 5.2-5.2Z" fill="#ffd600" />
      <path d="M44 18q14 0 14 16 0 8-6 12l-2 8H38l-2-8q-6-4-6-12 0-16 14-16Z" fill="#ffe9a8" stroke="#20304b" stroke-width="2.1" />
      <path d="M38 58h12v6H38Z" fill="#fffdf8" stroke="#20304b" stroke-width="1.7" />
      <path d="M40 68h8M42 73h4" fill="none" stroke="#20304b" stroke-width="1.8" stroke-linecap="round" />
      <circle cx="40" cy="34" r="1.6" fill="#20304b" />
      <circle cx="48" cy="34" r="1.6" fill="#20304b" />
      <path d="M40 42q4 4 8 0" fill="none" stroke="#20304b" stroke-width="1.6" stroke-linecap="round" />
      <path d="M28 24 22 18M60 24l6-6" fill="none" stroke="#78b8ed" stroke-width="1.8" stroke-linecap="round" />
    </g>
    <g v-else-if="name === 'run'">
      <path d="M12 62q18 10 40 8 18-2 28-12" fill="#7dd6fa" stroke="#20304b" stroke-width="1.6" />
      <path d="M64 18 68 8l4 10 10 3-10 3-4 10-4-10-10-3Z" fill="#ffd600" />
      <circle cx="38" cy="22" r="6.2" fill="#ffd0c8" stroke="#20304b" stroke-width="1.7" />
      <path d="M34 30 28 46l10 2 6-10 8 8 8-4" fill="none" stroke="#20304b" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
      <path d="M28 46 22 60M44 38l-2 18 10 8" fill="none" stroke="#20304b" stroke-width="2" stroke-linecap="round" />
      <path d="M58 36q6-8 10-6" fill="none" stroke="#20304b" stroke-width="1.6" />
      <path d="M70 42v18h6l2-8h-4" fill="#c4eed7" stroke="#20304b" stroke-width="1.5" />
    </g>
    <g v-else-if="name === 'science'">
      <path d="M70 14c1.6 3.2 2.4 4 5.6 5.6-3.2 1.6-4 2.4-5.6 5.6-1.6-3.2-2.4-4-5.6-5.6 3.2-1.6 4-2.4 5.6-5.6Z" fill="#ffd600" />
      <ellipse cx="44" cy="44" rx="18" ry="8" fill="none" stroke="#20304b" stroke-width="1.8" transform="rotate(-28 44 44)" />
      <ellipse cx="44" cy="44" rx="18" ry="8" fill="none" stroke="#5ea7e5" stroke-width="1.6" transform="rotate(28 44 44)" />
      <circle cx="44" cy="44" r="5.4" fill="#ab94de" stroke="#20304b" stroke-width="1.6" />
      <circle cx="28" cy="36" r="2.4" fill="#78b8ed" stroke="#20304b" stroke-width="1.1" />
      <circle cx="60" cy="52" r="2.4" fill="#f7b4ae" stroke="#20304b" stroke-width="1.1" />
      <path d="M18 70h52" fill="none" stroke="#20304b" stroke-width="1.5" stroke-linecap="round" />
    </g>
    <g v-else-if="name === 'hoop'">
      <path d="M70 16c1.5 3 2.2 3.8 5.2 5.2-3 1.4-3.7 2.2-5.2 5.2-1.5-3-2.2-3.8-5.2-5.2 3-1.4 3.7-2.2 5.2-5.2Z" fill="#ffd600" />
      <circle cx="44" cy="40" r="18" fill="#f7b4ae" stroke="#20304b" stroke-width="2" />
      <path d="M28 40h32M44 22v36M31 28l26 24M57 28 31 52" fill="none" stroke="#20304b" stroke-width="1.5" />
      <path d="M20 70h48" fill="none" stroke="#20304b" stroke-width="1.6" stroke-linecap="round" />
    </g>
    <g v-else>
      <path d="M70 14c1.6 3.2 2.4 4 5.6 5.6-3.2 1.6-4 2.4-5.6 5.6-1.6-3.2-2.4-4-5.6-5.6 3.2-1.6 4-2.4 5.6-5.6Z" fill="#ffd600" />
      <path d="M32 22h24l6 28H26Z" fill="#d0f1de" stroke="#20304b" stroke-width="2" />
      <path d="M38 30h12M36 40h16" fill="none" stroke="#20304b" stroke-width="1.6" stroke-linecap="round" />
      <path d="M28 58h32v10H28Z" fill="#fffdf8" stroke="#20304b" stroke-width="1.8" />
      <circle cx="44" cy="63" r="1.6" fill="#20304b" />
    </g>
  </svg>
</template>

<style scoped>
.art { width: 100%; height: 100%; overflow: visible; }
</style>
