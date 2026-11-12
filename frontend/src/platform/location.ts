import { Capacitor } from '@capacitor/core';
import { Geolocation, type PermissionStatus, type Position, type PositionOptions } from '@capacitor/geolocation';

/** A minimum, portable position shape. Do not persist or upload it here. */
export interface CurrentLocation {
  latitude: number;
  longitude: number;
  accuracy: number;
  timestamp: number;
  /** Degrees clockwise from true north, when the platform supplies it. */
  heading?: number;
}

export type LocationErrorCode = 'unsupported' | 'permission-denied' | 'unavailable' | 'timeout';

export type LocationResult =
  | { status: 'success'; location: CurrentLocation }
  | { status: 'error'; error: LocationErrorCode };

export type CurrentLocationOptions = Pick<PositionOptions,
  'enableHighAccuracy' | 'timeout' | 'maximumAge' | 'minimumUpdateInterval' | 'interval' | 'enableLocationFallback'>;

type PositionLike = Pick<Position, 'timestamp'> & {
  coords: Pick<Position['coords'], 'latitude' | 'longitude' | 'accuracy'> & { heading?: number | null };
};

/** The plugin surface used by the requester; the optional argument makes behavior testable. */
export interface LocationProvider {
  checkPermissions(): Promise<PermissionStatus>;
  requestPermissions(): Promise<PermissionStatus>;
  getCurrentPosition(options?: PositionOptions): Promise<PositionLike>;
}

export interface LocationWatchProvider extends LocationProvider {
  watchPosition(options: PositionOptions, callback: (position: PositionLike | null, error?: unknown) => void): Promise<string>;
  clearWatch(options: { id: string }): Promise<void>;
}

export type LocationWatchStop = () => Promise<void>;

export const defaultCurrentLocationOptions: CurrentLocationOptions = {
  // The map needs a usable on-campus point. On Android this also requests the
  // fine-location alias instead of accepting a roughly 100 m fused fix.
  enableHighAccuracy: true,
  timeout: 10_000,
  maximumAge: 0,
  // Android-specific watch cadence. Web and iOS safely ignore these fields.
  // Location providers may still coalesce callbacks to preserve battery.
  minimumUpdateInterval: 1_000,
  interval: 1_000,
};

/** GPS cold starts on Android can outlast the web timeout, especially indoors. */
export function resolveLocationOptions(options: CurrentLocationOptions = {}, platform = Capacitor.getPlatform()): PositionOptions {
  return { ...defaultCurrentLocationOptions,
    ...(platform === 'android' ? { timeout: 60_000, maximumAge: 15_000, enableLocationFallback: true } : {}),
    ...options };
}

function canRetryBalanced(error: unknown, options: PositionOptions) {
  return Capacitor.getPlatform() === 'android' && options.enableHighAccuracy
    && ['timeout', 'unavailable'].includes(mapError(error));
}

function balancedOptions(options: PositionOptions): PositionOptions {
  return { ...options, enableHighAccuracy: false, timeout: Math.min(options.timeout ?? 15_000, 15_000) };
}

async function requestPosition(provider: LocationProvider, options: PositionOptions): Promise<PositionLike> {
  try { return await provider.getCurrentPosition(options); }
  catch (error) {
    if (!canRetryBalanced(error, options)) throw error;
    return provider.getCurrentPosition(balancedOptions(options));
  }
}

function permissionGranted(status: PermissionStatus) {
  return status.location === 'granted' || status.coarseLocation === 'granted';
}

function mapError(error: unknown): LocationErrorCode {
  const value = error as { code?: string | number; message?: string } | undefined;
  const code = String(value?.code ?? '');
  const message = value?.message?.toLowerCase() ?? '';
  if (code === '1' || code === 'OS-PLUG-GLOC-0003' || /permission|denied/.test(message)) return 'permission-denied';
  if (code === '3' || code === 'OS-PLUG-GLOC-0010' || /timeout|timed out/.test(message)) return 'timeout';
  if (/unsupported|not implemented/.test(message)) return 'unsupported';
  return 'unavailable';
}

function toLocation(position: PositionLike): CurrentLocation | null {
  const { latitude, longitude, accuracy, heading } = position.coords;
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude) || !Number.isFinite(accuracy) || accuracy < 0
    || !Number.isFinite(position.timestamp)) return null;
  const normalizedHeading = typeof heading === 'number' && Number.isFinite(heading) ? ((heading % 360) + 360) % 360 : null;
  return { latitude, longitude, accuracy, timestamp: position.timestamp,
    ...(normalizedHeading === null ? {} : { heading: normalizedHeading }) };
}

function platformSupportsLocation(provider: LocationProvider) {
  if (provider !== Geolocation) return true;
  return Capacitor.isNativePlatform()
    || (typeof navigator !== 'undefined' && 'geolocation' in navigator);
}

function browserPosition(options: PositionOptions): Promise<PositionLike> {
  return new Promise((resolve, reject) => {
    navigator.geolocation.getCurrentPosition(resolve, reject, options);
  });
}

function reportWatchedPosition(
  listener: (result: LocationResult) => void,
  position: PositionLike | null,
  error?: unknown,
) {
  if (!position) {
    listener({ status: 'error', error: mapError(error) });
    return;
  }
  const location = toLocation(position);
  listener(location ? { status: 'success', location } : { status: 'error', error: 'unavailable' });
}

/**
 * Request one foreground position when a visible consumer needs it.
 *
 * Consumers call this function directly and branch on `status`; it keeps no
 * global location state, starts no watch, and never sends coordinates anywhere.
 */
export async function getCurrentLocation(
  options: CurrentLocationOptions = {},
  provider: LocationProvider = Geolocation,
): Promise<LocationResult> {
  if (!platformSupportsLocation(provider)) return { status: 'error', error: 'unsupported' };

  try {
    // Capacitor's Web implementation intentionally leaves requestPermissions()
    // unimplemented. The standard browser call both prompts and obtains one
    // foreground position, while native containers retain the plugin path.
    if (provider === Geolocation && !Capacitor.isNativePlatform()) {
      const location = toLocation(await browserPosition({ ...defaultCurrentLocationOptions, ...options }));
      return location ? { status: 'success', location } : { status: 'error', error: 'unavailable' };
    }

    let permission = await provider.checkPermissions();
    if (!permissionGranted(permission)) permission = await provider.requestPermissions();
    if (!permissionGranted(permission)) return { status: 'error', error: 'permission-denied' };

    const position = await requestPosition(provider, resolveLocationOptions(options));
    const location = toLocation(position);
    return location ? { status: 'success', location } : { status: 'error', error: 'unavailable' };
  } catch (error) {
    return { status: 'error', error: mapError(error) };
  }
}

/**
 * Watch foreground location changes until the returned function is called.
 *
 * The watcher only reports normalized results. It does not retain, upload, or
 * otherwise share coordinates; application lifecycle and state belong to the
 * caller.
 */
export async function watchCurrentLocation(
  listener: (result: LocationResult) => void,
  options: CurrentLocationOptions = {},
  provider: LocationWatchProvider = Geolocation,
): Promise<LocationWatchStop> {
  if (!platformSupportsLocation(provider)) {
    listener({ status: 'error', error: 'unsupported' });
    return async () => {};
  }

  const positionOptions = resolveLocationOptions(options);
  try {
    // Capacitor's web wrapper delegates to this same browser API but cannot
    // request permission itself. Calling the standard watcher prompts as needed.
    if (provider === Geolocation && !Capacitor.isNativePlatform()) {
      const id = navigator.geolocation.watchPosition(
        position => reportWatchedPosition(listener, position),
        error => reportWatchedPosition(listener, null, error),
        positionOptions,
      );
      return async () => { navigator.geolocation.clearWatch(id); };
    }

    let permission = await provider.checkPermissions();
    if (!permissionGranted(permission)) permission = await provider.requestPermissions();
    if (!permissionGranted(permission)) {
      listener({ status: 'error', error: 'permission-denied' });
      return async () => {};
    }

    let active = true, balancedAttempted = false, balancedPending = false, receivedPosition = false;
    let fallbackGeneration = 0;
    const id = await provider.watchPosition(positionOptions, (position, error) => {
      if (!active) return;
      // Keep the precise watch alive: a late GPS fix should still improve the
      // marker. Only one bounded balanced request is made per watch lifetime.
      if (position) receivedPosition = true;
      if (!position && ['permission-denied', 'unsupported'].includes(mapError(error))) fallbackGeneration++;
      if (!position && balancedPending && canRetryBalanced(error, positionOptions)) return;
      if (!position && !receivedPosition && !balancedAttempted && canRetryBalanced(error, positionOptions)) {
        balancedAttempted = true;
        balancedPending = true;
        const attempt = fallbackGeneration;
        void provider.getCurrentPosition(balancedOptions(positionOptions)).then(
          fallback => { if (active && attempt === fallbackGeneration) reportWatchedPosition(listener, fallback); },
          failure => { if (active && attempt === fallbackGeneration) reportWatchedPosition(listener, null, failure); },
        ).finally(() => { balancedPending = false; });
        return;
      }
      reportWatchedPosition(listener, position, error);
    });
    return async () => { if (!active) return; active = false; await provider.clearWatch({ id }); };
  } catch (error) {
    listener({ status: 'error', error: mapError(error) });
    return async () => {};
  }
}
