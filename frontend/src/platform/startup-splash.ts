import { Capacitor, registerPlugin } from '@capacitor/core';

interface StartupSplashPlugin {
  dismiss(): Promise<void>;
  fail(): Promise<void>;
}

const StartupSplash = registerPlugin<StartupSplashPlugin>('StartupSplash');

export function usesNativeStartupSplash(): boolean {
  return Capacitor.getPlatform() === 'android';
}

export function removeWebStartupSplash(): void {
  document.getElementById('startup-splash')?.remove();
}

export async function dismissNativeStartupSplash(): Promise<void> {
  try {
    await StartupSplash.dismiss();
  } catch {
    // The overlay is already gone, or this web build is running without the native plugin.
  }
}

export async function failNativeStartupSplash(): Promise<void> {
  try {
    await StartupSplash.fail();
  } catch {
    // Keep the native timeout as the fallback when the bridge call cannot be delivered.
  }
}
