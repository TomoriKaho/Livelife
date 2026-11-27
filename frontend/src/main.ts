import { createApp, nextTick } from 'vue';
import App from './App.vue';
import router from './router';
import { createSketchPlugin } from './plugins/sketch.js';
import './styles.css';
import { Capacitor } from '@capacitor/core';
import { loadAndroidConfig } from './platform/android-config';
import { setupAndroidNavigation } from './platform/android-navigation';
import { loadPreviewConfig } from './platform/runtime-config';
import { restoreSession } from './api/auth';
import { dismissNativeStartupSplash, failNativeStartupSplash, removeWebStartupSplash, usesNativeStartupSplash } from './platform/startup-splash';

// Configuration errors leave demo pages usable; the real API test stays disabled.
const configReady = Capacitor.isNativePlatform() && import.meta.env.VITE_ANDROID_TEST === 'true'
  ? loadAndroidConfig() : loadPreviewConfig();
const nativeSplash = usesNativeStartupSplash();
if (nativeSplash) removeWebStartupSplash();
function finishStartupSplash() {
  if (nativeSplash) {
    void dismissNativeStartupSplash();
    return;
  }
  const splash = document.getElementById('startup-splash');
  if (!splash) return;
  splash.classList.add('is-leaving');
  window.setTimeout(() => splash.remove(), 220);
}

async function startApp() {
  await configReady;
  await restoreSession();
  document.documentElement.dataset.sketchTheme ||= 'default';
  const app = createApp(App).use(router).use(createSketchPlugin());
  app.mount('#app');
  void setupAndroidNavigation(router);
  await router.isReady();
  await nextTick();
  requestAnimationFrame(() => requestAnimationFrame(finishStartupSplash));
}

void startApp().catch(() => {
  if (nativeSplash) {
    void failNativeStartupSplash();
    return;
  }
  document.getElementById('startup-splash')?.classList.add('has-error');
});
