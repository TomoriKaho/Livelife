import { createApp } from 'vue';
import App from './App.vue';
import router from './router';
import { createSketchPlugin } from './plugins/sketch.js';
import { createSketchBitmapQueue } from './plugins/sketch-bitmap';
import { warmSketchLayouts, waitSketchFont } from './plugins/sketch-warmup';
import './styles.css';
import { Capacitor } from '@capacitor/core';
import { loadAndroidConfig } from './platform/android-config';
import { setupAndroidNavigation } from './platform/android-navigation';
import { loadPreviewConfig } from './platform/runtime-config';

// Configuration errors leave demo pages usable; the real API test stays disabled.
const configReady = Capacitor.isNativePlatform() && import.meta.env.VITE_ANDROID_TEST === 'true'
  ? loadAndroidConfig() : loadPreviewConfig();
configReady.then(async () => {
  const started = performance.now();
  const status = document.createElement('div');
  status.setAttribute('role', 'status'); status.textContent = '正在载入整套界面缓存…';
  status.style.cssText = 'position:fixed;inset:0;display:grid;place-items:center;background:#f8f4ea;color:#20304b;font:16px sans-serif';
  document.body.append(status);
  await waitSketchFont();
  const fontReady = document.fonts.check('16px "LiveLife Rounded"');
  const bitmaps = createSketchBitmapQueue();
  let restored = false;
  try {
    if (fontReady) restored = await bitmaps.restore((done, total) => { status.textContent = `正在载入整套界面缓存（${done}/${total}）…`; });
  } finally { status.remove(); }
  // All default PNGs are decoded before mounting. A compatible boot creates no
  // hidden pages and never defers default decorations until the first visit.
  if (!restored) {
    if (await warmSketchLayouts(App, router.options.routes, bitmaps) && fontReady && document.fonts.check('16px "LiveLife Rounded"')) await bitmaps.markPrepared();
  }
  console.info('Livelife sketch preparation', JSON.stringify({ ...bitmaps.stats, elapsedMs: Math.round(performance.now() - started) }));
  const app = createApp(App).use(router).use(createSketchPlugin(bitmaps));
  app.onUnmount(() => bitmaps.dispose());
  app.mount('#app');
  void setupAndroidNavigation(router);
  requestAnimationFrame(() => requestAnimationFrame(async () => {
    await bitmaps.whenIdle();
    console.info('Livelife sketch first page', JSON.stringify({ ...bitmaps.stats, elapsedMs: Math.round(performance.now() - started) }));
  }));
});
