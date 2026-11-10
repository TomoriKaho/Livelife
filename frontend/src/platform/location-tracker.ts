import { ref, shallowRef } from 'vue';
import {
  getCurrentLocation,
  watchCurrentLocation,
  type CurrentLocation,
  type LocationErrorCode,
  type LocationWatchStop,
} from './location';

export type LocationTrackingState = 'idle' | 'locating' | 'located' | LocationErrorCode;

/** The most recent foreground position for the lifetime of the mounted app. */
export const currentLocation = shallowRef<CurrentLocation | null>(null);
export const locationTrackingState = ref<LocationTrackingState>('idle');

let stopWatch: LocationWatchStop | null = null;
let starting: Promise<void> | null = null;
let startingGeneration: number | null = null;
let generation = 0;

/** Start one shared foreground watch. Repeated calls keep the existing watch. */
export function startLocationTracking(): Promise<void> {
  if (stopWatch) return Promise.resolve();
  if (starting && startingGeneration === generation) return starting;

  const watchGeneration = ++generation;
  startingGeneration = watchGeneration;
  locationTrackingState.value = 'locating';
  starting = watchCurrentLocation(result => {
    if (watchGeneration !== generation) return;
    if (result.status === 'success') {
      currentLocation.value = result.location;
      locationTrackingState.value = 'located';
    } else {
      locationTrackingState.value = result.error;
    }
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
  locationTrackingState.value = 'locating';
  const result = await getCurrentLocation();
  if (result.status === 'success') {
    currentLocation.value = result.location;
    locationTrackingState.value = 'located';
  } else {
    locationTrackingState.value = result.error;
  }
  return result;
}
