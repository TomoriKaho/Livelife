import { project } from './geometry.mjs';

// Device geolocation is WGS-84 latitude/longitude. The campus snapshot uses
// the same local-meter projection as its OSM source data.
export function toDeviceMapLocation({ latitude, longitude, accuracy }) {
  if (![latitude, longitude, accuracy].every(Number.isFinite) || accuracy < 0) return null;
  return { point: project({ lon: longitude, lat: latitude }), accuracy };
}

// Keep a non-zero area visible when a platform reports a zero-meter estimate.
export function accuracyRadius(accuracy) {
  return Math.max(1, Number.isFinite(accuracy) ? accuracy : 1);
}
