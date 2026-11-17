import { ref, shallowRef } from 'vue';
import {
  getCurrentLocation,
  watchCurrentLocation,
  type CurrentLocation,
  type LocationErrorCode,
  type LocationResult,
  type LocationWatchStop,
} from './location.ts';

export type LocationTrackingState = 'idle' | 'locating' | 'located' | LocationErrorCode;

/** The most recent foreground position for the lifetime of the mounted app. */
export const currentLocation = shallowRef<CurrentLocation | null>(null);
export const locationTrackingState = ref<LocationTrackingState>('idle');

let stopWatch: LocationWatchStop | null = null;
let starting: Promise<void> | null = null;
let startingGeneration: number | null = null;
let generation = 0;

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
  if (stopWatch) return Promise.resolve();
  if (starting && startingGeneration === generation) return starting;

  const watchGeneration = ++generation;
  startingGeneration = watchGeneration;
  if (!currentLocation.value) locationTrackingState.value = 'locating';
  starting = watchCurrentLocation(result => {
    if (watchGeneration !== generation) return;
    publishLocationResult(result);
  }).then(async stop => {
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
  if (!currentLocation.value) locationTrackingState.value = 'locating';
  const result = await getCurrentLocation();
  publishLocationResult(result, 'request');
  return result;
}
