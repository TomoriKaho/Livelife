import { createApp } from 'vue';
import App from './App.vue';
import router from './router';
import { createSketchPlugin } from './plugins/sketch.js';
import { createSketchBitmapQueue } from './plugins/sketch-bitmap';
import { warmSketchLayouts } from './plugins/sketch-warmup';
import './styles.css';
import { Capacitor } from '@capacitor/core';
import { loadAndroidConfig } from './platform/android-config';
import { setupAndroidNavigation } from './platform/android-navigation';
import { loadPreviewConfig } from './platform/runtime-config';

// Configuration errors leave demo pages usable; the real API test stays disabled.
const configReady = Capacitor.isNativePlatform() && import.meta.env.VITE_ANDROID_TEST === 'true'
  ? loadAndroidConfig() : loadPreviewConfig();
configReady.then(async () => {
  const bitmaps = createSketchBitmapQueue();
  await warmSketchLayouts(App, router.options.routes, bitmaps);
  const app = createApp(App).use(router).use(createSketchPlugin(bitmaps));
  app.onUnmount(() => bitmaps.dispose());
  app.mount('#app');
  void setupAndroidNavigation(router);
});
