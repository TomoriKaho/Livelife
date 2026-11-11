import { contains, project } from './geometry.mjs';

function segmentDistance(point, start, end) {
  const dx = end[0] - start[0], dz = end[1] - start[1];
  const length = dx * dx + dz * dz;
  const ratio = length ? Math.max(0, Math.min(1, ((point[0] - start[0]) * dx + (point[1] - start[1]) * dz) / length)) : 0;
  return Math.hypot(point[0] - start[0] - ratio * dx, point[1] - start[1] - ratio * dz);
}

function ringDistance(point, ring) {
  let distance = Infinity;
  for (let i = 0; i < ring.length; i++) distance = Math.min(distance, segmentDistance(point, ring[i], ring[(i + 1) % ring.length]));
  return distance;
}

export function buildingDistance(point, building) {
  if (contains(point, building.points) && !(building.holes || []).some(hole => contains(point, hole))) return 0;
  return Math.min(ringDistance(point, building.points), ...(building.holes || []).map(hole => ringDistance(point, hole)));
}

export function nearestNamedBuildings(buildings, point, limit = 5) {
  return buildings.filter(building => building.name?.trim()).map(building => ({
    id: building.id,
    name: building.name,
    distance: buildingDistance(point, building),
  })).sort((a, b) => a.distance - b.distance || a.id.localeCompare(b.id)).slice(0, limit);
}

export function campusPoint(longitude, latitude, boundary) {
  if (!Number.isFinite(longitude) || !Number.isFinite(latitude)) return null;
  const point = project({ lon: longitude, lat: latitude });
  return contains(point, boundary) ? point : null;
}

function normalize(text) {
  return text.normalize('NFKC').toLowerCase().replace(/[^\p{L}\p{N}]/gu, '');
}

function nameVariants(name) {
  const match = /^([^（(]+)[（(]([^）)]+)[）)]/.exec(name);
  const names = match ? [name, match[1], match[2]] : [name];
  return [...new Set(names.map(normalize).filter(value => value.length >= 3))];
}

function includesName(text, name) {
  for (let start = text.indexOf(name); start >= 0; start = text.indexOf(name, start + 1)) {
    if (!/^\d/u.test(name) || start === 0 || !/\d/u.test(text[start - 1])) return true;
  }
  return false;
}

export function matchBuildingId(location, buildings) {
  if (!location) return null;
  const text = normalize(location);
  let length = 0, matches = new Set();
  for (const building of buildings) {
    for (const name of nameVariants(building.name || '')) {
      if (!includesName(text, name)) continue;
      if (name.length > length) { length = name.length; matches = new Set([building.id]); }
      else if (name.length === length) matches.add(building.id);
    }
  }
  return matches.size === 1 ? [...matches][0] : null;
}

export function matchActivities(records, buildings) {
  return records.flatMap(record => {
    const building = matchBuildingId(record.location, buildings);
    return building ? [{ ...record, building }] : [];
  }).sort((a, b) => Date.parse(a.start_at) - Date.parse(b.start_at) || a.id.localeCompare(b.id));
}
