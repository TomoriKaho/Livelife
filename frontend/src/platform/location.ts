import { Capacitor, registerPlugin } from '@capacitor/core';
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
  // Prefer GPS where authorized, while Android also subscribes to OEM network
  // fixes so indoor acquisition does not depend on a satellite fix.
  enableHighAccuracy: true,
  timeout: 10_000,
  maximumAge: 0,
  // Android-specific watch cadence. Web and iOS safely ignore these fields.
  // Location providers may still coalesce callbacks to preserve battery.
  minimumUpdateInterval: 1_000,
  interval: 1_000,
};

/** Android uses a bounded system-provider request and a recent monotonic-age cache. */
export function resolveLocationOptions(options: CurrentLocationOptions = {}, platform = Capacitor.getPlatform()): PositionOptions {
  return { ...defaultCurrentLocationOptions,
    ...(platform === 'android' ? { timeout: 20_000, maximumAge: 15_000 } : {}),
    ...options };
}

type AndroidLocationEvent = PositionLike | { error: LocationErrorCode };
interface AndroidLocationBridge extends Omit<LocationWatchProvider, 'watchPosition'> {
  watchPosition(options: PositionOptions, callback: (event: AndroidLocationEvent | null, error?: unknown) => void): Promise<string>;
}

/** Keep native watch errors as events: a timed-out watch can still deliver GPS later. */
export function createAndroidLocationProvider(bridge: AndroidLocationBridge): LocationWatchProvider {
  return {
    checkPermissions: () => bridge.checkPermissions(),
    requestPermissions: () => bridge.requestPermissions(),
    getCurrentPosition: options => bridge.getCurrentPosition(options),
    watchPosition: (options, callback) => bridge.watchPosition(options, (event, error) => {
      if (event && 'error' in event) callback(null, { code: event.error });
      else callback(event, error);
    }),
    clearWatch: options => bridge.clearWatch(options),
  };
}

const androidLocation = createAndroidLocationProvider(registerPlugin<AndroidLocationBridge>('DeviceLocation'));
function defaultProvider(): LocationWatchProvider {
  return Capacitor.getPlatform() === 'android' ? androidLocation : Geolocation;
}

function permissionGranted(status: PermissionStatus) {
  return status.location === 'granted' || status.coarseLocation === 'granted';
}

function mapError(error: unknown): LocationErrorCode {
  const value = error as { code?: string | number; message?: string } | undefined;
  const code = String(value?.code ?? '');
  if (['unsupported', 'permission-denied', 'unavailable', 'timeout'].includes(code)) return code as LocationErrorCode;
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
  provider: LocationProvider = defaultProvider(),
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

    const position = await provider.getCurrentPosition(resolveLocationOptions(options));
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
  provider: LocationWatchProvider = defaultProvider(),
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

    let active = true;
    const id = await provider.watchPosition(positionOptions, (position, error) => {
      if (active) reportWatchedPosition(listener, position, error);
    });
    return async () => { if (!active) return; active = false; await provider.clearWatch({ id }); };
  } catch (error) {
    listener({ status: 'error', error: mapError(error) });
    return async () => {};
  }
}
