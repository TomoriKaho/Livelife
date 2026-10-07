import { createApp } from 'vue';
import App from './App.vue';
import router from './router';
import { createSketchPlugin } from './plugins/sketch.js';
import './styles.css';
import { Capacitor } from '@capacitor/core';
import { loadAndroidConfig } from './platform/android-config';
import { setupAndroidNavigation } from './platform/android-navigation';
import { loadPreviewConfig } from './platform/runtime-config';

// Configuration errors leave demo pages usable; the real API test stays disabled.
const configReady = Capacitor.isNativePlatform() && import.meta.env.VITE_ANDROID_TEST === 'true'
  ? loadAndroidConfig() : loadPreviewConfig();
configReady.then(() => {
  createApp(App).use(router).use(createSketchPlugin()).mount('#app');
  void setupAndroidNavigation(router);
});
