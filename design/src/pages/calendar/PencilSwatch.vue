<script setup>
import { useId } from 'vue';

const props = defineProps({
  pencil: { type: String, required: true },
});

const fills = {
  yellow: '#fbd21a',
  blue: '#5ea7e5',
  mint: '#88cbb2',
  pink: '#e99796',
  lavender: '#ab94de',
};

const fid = `swatch-${useId().replace(/[^a-zA-Z0-9_-]/g, '')}`;
</script>

<template>
  <svg class="swatch" viewBox="0 0 12 12" aria-hidden="true">
    <defs>
      <filter :id="fid" x="-20%" y="-20%" width="140%" height="140%" color-interpolation-filters="sRGB">
        <feTurbulence type="fractalNoise" baseFrequency=".9" numOctaves="3" seed="7" result="paper" />
        <feColorMatrix in="paper" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  .28 .53 .19 0 0" />
        <feComponentTransfer>
          <feFuncA type="linear" slope="2.4" intercept="-.42" />
        </feComponentTransfer>
        <feComposite in="SourceGraphic" operator="in" />
      </filter>
    </defs>
    <circle cx="6.1" cy="6" r="4.7" :fill="fills[props.pencil]" :filter="`url(#${fid})`" />
    <circle cx="6.6" cy="5.4" r="2.4" :fill="fills[props.pencil]" opacity=".38" />
  </svg>
</template>

<style scoped>
.swatch { width: 10px; height: 10px; display: block; flex: none; }
</style>
