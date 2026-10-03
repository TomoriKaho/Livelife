// 本地坐标：x 向东、z 向南，单位米；不使用在线地图底图或瓦片。
export const origin = [116.304, 39.9915];
export function project({ lon, lat }) {
  return [(lon - origin[0]) * 111320 * Math.cos(origin[1] * Math.PI / 180), -(lat - origin[1]) * 111320];
}
export function contains(point, polygon) {
  let inside = false;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const a = polygon[i], b = polygon[j];
    if ((a[1] > point[1]) !== (b[1] > point[1]) && point[0] < (b[0] - a[0]) * (point[1] - a[1]) / (b[1] - a[1]) + a[0]) inside = !inside;
  }
  return inside;
}
// 保留校内点；校外点投影到最近校界。凹形边界也适用，不用矩形范围替代校界。
export function constrainToBoundary(point, polygon) {
  if (contains(point, polygon)) return [...point];
  let nearest = [...point], distance = Infinity;
  for (let i = 0; i < polygon.length; i++) {
    const a = polygon[i], b = polygon[(i + 1) % polygon.length];
    const dx = b[0] - a[0], dz = b[1] - a[1], lengthSquared = dx * dx + dz * dz;
    if (!lengthSquared) continue;
    const t = Math.max(0, Math.min(1, ((point[0] - a[0]) * dx + (point[1] - a[1]) * dz) / lengthSquared));
    const candidate = [a[0] + t * dx, a[1] + t * dz];
    const squared = (candidate[0] - point[0]) ** 2 + (candidate[1] - point[1]) ** 2;
    if (squared < distance) { nearest = candidate; distance = squared; }
  }
  return nearest;
}
export function center(points) {
  const ring = points.length > 1 && points[0][0] === points.at(-1)[0] && points[0][1] === points.at(-1)[1] ? points.slice(0, -1) : points;
  return ring.reduce((sum, p) => [sum[0] + p[0] / ring.length, sum[1] + p[1] / ring.length], [0, 0]);
}
// 与指定范围逐段求交：可生成校内统计道路，也可保留下载范围内连续的渲染道路。
export function clipRoad(points, boundary) {
  const result = [];
  const cross = (a, b) => a[0] * b[1] - a[1] * b[0];
  for (let i = 1; i < points.length; i++) {
    const a = points[i - 1], b = points[i], r = [b[0] - a[0], b[1] - a[1]], cuts = [0, 1];
    for (let j = 0; j < boundary.length; j++) {
      const c = boundary[j], d = boundary[(j + 1) % boundary.length];
      const s = [d[0] - c[0], d[1] - c[1]], ca = [c[0] - a[0], c[1] - a[1]], denominator = cross(r, s);
      if (Math.abs(denominator) < 1e-8) continue;
      const t = cross(ca, s) / denominator, u = cross(ca, r) / denominator;
      if (t > 0 && t < 1 && u >= 0 && u <= 1) cuts.push(t);
    }
    cuts.sort((x, y) => x - y);
    const at = t => [a[0] + r[0] * t, a[1] + r[1] * t];
    for (let k = 1; k < cuts.length; k++) {
      if (cuts[k] - cuts[k - 1] > 1e-7 && contains(at((cuts[k] + cuts[k - 1]) / 2), boundary)) result.push([at(cuts[k - 1]), at(cuts[k])]);
    }
  }
  return result;
}
