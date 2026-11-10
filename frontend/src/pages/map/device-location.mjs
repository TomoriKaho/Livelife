import { project } from './geometry.mjs';
import { insideFootprint } from './rings.mjs';

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

export function orientationHeading(event, screenAngle = 0) {
  const rotation = normalizeHeading(screenAngle) ?? 0;
  const compassHeading = normalizeHeading(event?.webkitCompassHeading);
  if (compassHeading !== null) return normalizeHeading(compassHeading + rotation);
  // Chromium DevTools and many Android browsers expose alpha without marking
  // it absolute. It still represents a useful, continuously changing device
  // direction when no calibrated compass heading is available. alpha is
  // relative to the device's portrait axis, so account for display rotation.
  const alpha = normalizeHeading(event?.alpha);
  return alpha === null ? null : normalizeHeading(360 - alpha + rotation);
}

/** Keep a live compass heading when a fresh geolocation response omits one. */
export function preserveHeading(location, fallbackHeading) {
  const heading = normalizeHeading(location?.heading) ?? normalizeHeading(fallbackHeading);
  return { ...location, ...(heading === null ? {} : { heading }) };
}

/** Return the campus building containing a projected device point, if any. */
export function buildingAtDeviceLocation(point, buildings) {
  if (!Array.isArray(point) || point.length !== 2 || !point.every(Number.isFinite) || !Array.isArray(buildings)) return null;
  return buildings.find(building => insideFootprint(point, building)) || null;
}
