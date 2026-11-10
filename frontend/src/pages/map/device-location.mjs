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

function distanceToRing(point, ring) {
  let distance = Infinity;
  for (let index = 0; index < ring.length; index++) {
    const [ax, az] = ring[index], [bx, bz] = ring[(index + 1) % ring.length];
    const dx = bx - ax, dz = bz - az, lengthSquared = dx ** 2 + dz ** 2;
    const ratio = lengthSquared ? Math.max(0, Math.min(1, ((point[0] - ax) * dx + (point[1] - az) * dz) / lengthSquared)) : 0;
    distance = Math.min(distance, Math.hypot(point[0] - ax - dx * ratio, point[1] - az - dz * ratio));
  }
  return distance;
}

/** Return every building whose footprint intersects the displayed accuracy circle. */
export function buildingsAtDeviceLocation(point, accuracy, buildings) {
  if (!Array.isArray(point) || point.length !== 2 || !point.every(Number.isFinite) || !Array.isArray(buildings)) return [];
  const radius = accuracyRadius(accuracy);
  return buildings.filter(building => insideFootprint(point, building)
    || [building.points, ...(building.holes || [])].some(ring => distanceToRing(point, ring) <= radius));
}
