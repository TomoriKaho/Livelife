import { contains } from './geometry.mjs';

// OSM multipolygon 的同一圈可能拆为多个方向不一致的 way。
export function joinRings(segments) {
  const pending = segments.filter(s => s.length > 1).map(s => s.map(p => [...p]));
  const rings = [], same = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]) < .01;
  while (pending.length) {
    const ring = pending.shift();
    while (!same(ring[0], ring.at(-1))) {
      const index = pending.findIndex(s => same(ring.at(-1), s[0]) || same(ring.at(-1), s.at(-1)));
      if (index < 0) break;
      const next = pending.splice(index, 1)[0];
      if (!same(ring.at(-1), next[0])) next.reverse();
      ring.push(...next.slice(1));
    }
    // 不把缺失成员的开放折线虚构为建筑轮廓。
    if (ring.length >= 4 && same(ring[0], ring.at(-1))) rings.push(ring);
  }
  return rings;
}
export function insideFootprint(point, building) {
  return contains(point, building.points) && !(building.holes || []).some(h => contains(point, h));
}
