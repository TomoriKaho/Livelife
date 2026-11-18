import { ref, shallowRef } from 'vue';
import {
  watchCurrentLocation,
  type CurrentLocation,
  type LocationErrorCode,
  type LocationResult,
  type LocationWatchStop,
} from './location.ts';

export type LocationTrackingState = 'disabled' | 'idle' | 'locating' | 'located' | LocationErrorCode;

const PREFERENCE_KEY = 'livelife.location.enabled';
function readPreference() {
  try {
    const saved = globalThis.localStorage?.getItem(PREFERENCE_KEY);
    return saved == null || saved === 'true';
  }
  catch { return false; }
}
export const locationEnabled = ref(readPreference());

/** The most recent foreground position for the lifetime of the mounted app. */
export const currentLocation = shallowRef<CurrentLocation | null>(null);
export const locationTrackingState = ref<LocationTrackingState>(locationEnabled.value ? 'idle' : 'disabled');

let stopWatch: LocationWatchStop | null = null;
let starting: Promise<void> | null = null;
let startingGeneration: number | null = null;
let generation = 0;
let watchController: AbortController | null = null;
const pendingRequests = new Set<() => void>();

export async function setLocationEnabled(enabled: boolean) {
  locationEnabled.value = enabled;
  try { globalThis.localStorage?.setItem(PREFERENCE_KEY, String(enabled)); }
  catch { /* The in-memory preference still applies when storage is unavailable. */ }
  if (enabled) await startLocationTracking();
  else {
    const stopped = stopLocationTracking();
    currentLocation.value = null;
    locationTrackingState.value = 'disabled';
    await stopped;
  }
}

if (typeof window !== 'undefined') window.addEventListener('storage', event => {
  if (event.key === PREFERENCE_KEY || event.key === null) void setLocationEnabled(readPreference());
});

/** Only return a position that the application is currently allowed to use. */
export function usableCurrentLocation(now = Date.now()) {
  const point = currentLocation.value;
  const age = point ? now - point.timestamp : Infinity;
  return locationEnabled.value && locationTrackingState.value === 'located' && age >= -10000 && age <= 120000 ? point : null;
}

/**
 * Fold a platform result into the shared foreground location state.
 *
 * A watch can report a cached fix after a newer GPS result, or report a
 * transient timeout after it has already produced a usable fix.  Neither
 * event should move the marker backwards or replace the usable "located"
 * state shown to the user.  Permission and platform errors remain visible.
 */
export function applyLocationResult(
  current: CurrentLocation | null,
  result: LocationResult,
  { source = 'watch', state = 'located' }: { source?: 'watch' | 'request'; state?: LocationTrackingState } = {},
): { location: CurrentLocation | null; state: LocationTrackingState } {
  if (result.status === 'success') {
    if (current && result.location.timestamp <= current.timestamp) {
      return { location: current, state: 'located' };
    }
    return { location: result.location, state: 'located' };
  }

  // Browser and fused-location watches are long lived: a single timeout or
  // temporarily unavailable provider after a valid fix is not a loss of the
  // already known foreground position.  Surface errors that require user
  // action (permission) or mean the capability is absent instead.
  if (source === 'watch' && current && (result.error === 'timeout' || result.error === 'unavailable')) {
    return { location: current, state };
  }
  return { location: current, state: result.error };
}

function publishLocationResult(result: LocationResult, source: 'watch' | 'request' = 'watch') {
  const next = applyLocationResult(currentLocation.value, result, { source, state: locationTrackingState.value });
  if (next.location !== currentLocation.value) currentLocation.value = next.location;
  locationTrackingState.value = next.state;
}

/** Start one shared foreground watch. Repeated calls keep the existing watch. */
export function startLocationTracking(): Promise<void> {
  if (!locationEnabled.value) return Promise.resolve();
  if (stopWatch) return Promise.resolve();
  if (starting && startingGeneration === generation) return starting;

  const watchGeneration = ++generation;
  watchController = new AbortController();
  startingGeneration = watchGeneration;
  if (!currentLocation.value) locationTrackingState.value = 'locating';
  starting = watchCurrentLocation(result => {
    if (watchGeneration !== generation) return;
    publishLocationResult(result);
  }, {}, undefined, watchController.signal).then(async stop => {
    if (watchGeneration !== generation) {
      await stop();
      return;
    }
    stopWatch = stop;
  }).finally(() => {
    if (startingGeneration === watchGeneration) {
      starting = null;
      startingGeneration = null;
    }
  });
  return starting;
}

/** Stop the shared watch, including one that is still waiting to initialize. */
export async function stopLocationTracking() {
  generation++;
  watchController?.abort();
  watchController = null;
  for (const cancel of pendingRequests) cancel();
  starting = null;
  startingGeneration = null;
  const stop = stopWatch;
  stopWatch = null;
  await stop?.();
}

/** Recreate the watch after the user asks to retry location access. */
export async function restartLocationTracking() {
  await stopLocationTracking();
  await startLocationTracking();
}

/** Obtain one fresh foreground fix and publish it to every active consumer. */
export async function refreshCurrentLocation() {
  if (!locationEnabled.value) return { status: 'error', error: 'disabled' } as const;
  if (!currentLocation.value) locationTrackingState.value = 'locating';
  const requestGeneration = generation;
  // A temporary watch is cancellable on both Web and Android, unlike a native
  // getCurrentPosition request. Release it immediately after its first result.
  return new Promise<LocationResult | { status: 'error'; error: 'disabled' }>(resolve => {
    const controller = new AbortController();
    let finished = false;
    let stop: LocationWatchStop | undefined;
    const finish = (result: LocationResult | { status: 'error'; error: 'disabled' }) => {
      if (finished) return;
      finished = true;
      controller.abort();
      pendingRequests.delete(cancel);
      void stop?.();
      if (!(result.status === 'error' && result.error === 'disabled') && requestGeneration === generation && locationEnabled.value) {
        publishLocationResult(result as LocationResult, 'request');
      }
      resolve(result);
    };
    const cancel = () => finish({ status: 'error', error: 'disabled' });
    pendingRequests.add(cancel);
    void watchCurrentLocation(result => finish(result), {}, undefined, controller.signal).then(cleanup => {
      stop = cleanup;
      if (finished) void cleanup();
    });
  });
}
