import { createApp } from 'vue';
import App from './App.vue';
import router from './router';
import { createSketchPlugin } from './plugins/sketch.js';
import './styles.css';
import { loadPreviewConfig } from './platform/runtime-config';

// Configuration errors leave demo pages usable; the real API test stays disabled.
loadPreviewConfig().then(() => createApp(App).use(router).use(createSketchPlugin()).mount('#app'));
