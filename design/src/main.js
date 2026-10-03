import { createApp } from 'vue';
import App from './App.vue';
import router from './router/index.js';
import { createSketchPlugin } from './plugins/sketch.js';
import '../styles.css';

createApp(App).use(router).use(createSketchPlugin()).mount('#app');
