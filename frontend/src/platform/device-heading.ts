import { Capacitor, registerPlugin, type PluginListenerHandle } from '@capacitor/core';

type AndroidHeadingEvent = { heading?: number };

interface DeviceHeadingPlugin {
  start(): Promise<{ available: boolean }>;
  stop(): Promise<void>;
  addListener(eventName: 'heading', listenerFunc: (event: AndroidHeadingEvent) => void): Promise<PluginListenerHandle>;
}

const DeviceHeading = registerPlugin<DeviceHeadingPlugin>('DeviceHeading');

export type DeviceHeadingStop = () => Promise<void>;

/**
 * Subscribe to the Android rotation-vector sensor when inside the Capacitor
 * Android shell. A missing sensor or native bridge is not an error: callers
 * can continue with the WebView deviceorientation fallback.
 */
export async function watchAndroidDeviceHeading(listener: (heading: number) => void): Promise<DeviceHeadingStop | null> {
  if (Capacitor.getPlatform() !== 'android') return null;

  let handle: PluginListenerHandle | undefined;
  try {
    handle = await DeviceHeading.addListener('heading', event => {
      if (typeof event.heading === 'number' && Number.isFinite(event.heading)) listener(event.heading);
    });
    const { available } = await DeviceHeading.start();
    if (!available) {
      await handle.remove();
      return null;
    }
    return async () => {
      await Promise.allSettled([handle!.remove(), DeviceHeading.stop()]);
    };
  } catch {
    await handle?.remove();
    return null;
  }
}
