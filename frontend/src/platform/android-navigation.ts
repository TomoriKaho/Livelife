import { App } from '@capacitor/app';
import { Capacitor } from '@capacitor/core';
import type { Router } from 'vue-router';
import { checkAndroidStatus } from './android-config';

// Page handlers run in reverse registration order: overlays before navigation.
const handlers: (() => boolean)[] = [];
export function registerBackHandler(handler: () => boolean) {
  handlers.push(handler);
  return () => { const i = handlers.indexOf(handler); if (i >= 0) handlers.splice(i, 1); };
}
export async function setupAndroidNavigation(router: Router) {
  if (!Capacitor.isNativePlatform()) return;
  await App.addListener('backButton', () => {
    for (const handler of [...handlers].reverse()) if (handler()) return;
    if (router.options.history.state.back) router.back();
    else if (window.confirm('退出 Livelife 测试？')) void App.exitApp();
  });
  await App.addListener('appStateChange', ({ isActive }) => {
    if (isActive) void checkAndroidStatus().catch(() => {});
  });
}
