import { Capacitor } from '@capacitor/core';
import { Geolocation, type PermissionStatus, type Position, type PositionOptions } from '@capacitor/geolocation';

/** A minimum, portable position shape. Do not persist or upload it here. */
export interface CurrentLocation {
  latitude: number;
  longitude: number;
  accuracy: number;
  timestamp: number;
}

export type LocationErrorCode = 'unsupported' | 'permission-denied' | 'unavailable' | 'timeout';

export type LocationResult =
  | { status: 'success'; location: CurrentLocation }
  | { status: 'error'; error: LocationErrorCode };

export type CurrentLocationOptions = Pick<PositionOptions, 'enableHighAccuracy' | 'timeout' | 'maximumAge'>;

type PositionLike = Pick<Position, 'timestamp'> & {
  coords: Pick<Position['coords'], 'latitude' | 'longitude' | 'accuracy'>;
};

/** The plugin surface used by the requester; the optional argument makes behavior testable. */
export interface LocationProvider {
  checkPermissions(): Promise<PermissionStatus>;
  requestPermissions(): Promise<PermissionStatus>;
  getCurrentPosition(options?: PositionOptions): Promise<PositionLike>;
}

export const defaultCurrentLocationOptions: Required<CurrentLocationOptions> = {
  enableHighAccuracy: false,
  timeout: 10_000,
  maximumAge: 0,
};

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
  const { latitude, longitude, accuracy } = position.coords;
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude) || !Number.isFinite(accuracy) || accuracy < 0
    || !Number.isFinite(position.timestamp)) return null;
  return { latitude, longitude, accuracy, timestamp: position.timestamp };
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

    const position = await provider.getCurrentPosition({ ...defaultCurrentLocationOptions, ...options });
    const location = toLocation(position);
    return location ? { status: 'success', location } : { status: 'error', error: 'unavailable' };
  } catch (error) {
    return { status: 'error', error: mapError(error) };
  }
}
