<script setup>
defineProps({ label: { type: String, required: true } });
const enabled = defineModel({ type: Boolean, default: false });
</script>
<template><button class="preference-switch" type="button" role="switch" :aria-label="label" :aria-checked="enabled" @click="enabled = !enabled"><span v-sketch class="switch-track sketch" :data-pencil="enabled ? 'mint' : undefined" aria-hidden="true"><span v-sketch class="switch-knob sketch" :class="{ enabled }" :data-pencil="enabled ? 'blue' : undefined"></span></span></button></template>
<style scoped>
.preference-switch { display: grid; place-items: center; width: 54px; height: 44px; flex: none; padding: 0; border: 0; background: transparent; }
.switch-track { position: relative; display: block; width: 48px; height: 32px; pointer-events: none; }
.switch-knob { position: absolute; left: 4px; top: 4px; display: block; width: 22px; height: 22px; transition: transform .2s ease; }
.switch-knob.enabled { transform: translateX(17px); }
@media(prefers-reduced-motion:reduce) { .switch-knob { transition: none; } }
</style>
