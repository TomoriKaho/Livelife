import { project } from './geometry.mjs';

// Device geolocation is WGS-84 latitude/longitude. The campus snapshot uses
// the same local-meter projection as its OSM source data.
export function toDeviceMapLocation({ latitude, longitude, accuracy, heading }) {
  if (![latitude, longitude, accuracy].every(Number.isFinite) || accuracy < 0) return null;
  const normalizedHeading = normalizeHeading(heading);
  return { point: project({ lon: longitude, lat: latitude }), accuracy,
    ...(normalizedHeading === null ? {} : { heading: normalizedHeading }) };
}

// Keep a non-zero area visible when a platform reports a zero-meter estimate.
export function accuracyRadius(accuracy) {
  return Math.max(1, Number.isFinite(accuracy) ? accuracy : 1);
}

export function normalizeHeading(heading) {
  return Number.isFinite(heading) ? ((heading % 360) + 360) % 360 : null;
}

export function orientationHeading(event) {
  const compassHeading = normalizeHeading(event?.webkitCompassHeading);
  if (compassHeading !== null) return compassHeading;
  // Chromium DevTools and many Android browsers expose alpha without marking
  // it absolute. It still represents a useful, continuously changing device
  // direction when no calibrated compass heading is available.
  return normalizeHeading(360 - event?.alpha);
}
