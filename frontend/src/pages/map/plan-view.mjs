import { constrainToBoundary } from './geometry.mjs';
import { insideFootprint } from './rings.mjs';

export const planLimits = { minScale: .22, maxScale: 3.2 };
export const initialPlanScale = width => Math.max(planLimits.minScale, Math.min(1, width / 720));
export function planAnchor(width, height, inset = 0) {
  return [width / 2, 100 + Math.max(40, height - inset - 100) / 2];
}
export function worldToPlan(point, view, anchor) {
  return point.map((value, i) => (value - view.center[i]) * view.scale + anchor[i]);
}
export function planToWorld(point, view, anchor) {
  return point.map((value, i) => (value - anchor[i]) / view.scale + view.center[i]);
}
// 缩放围绕手指/鼠标下的地点进行，避免地图以屏幕中点跳动。
export function zoomPlan(view, scale, point, anchor, boundary) {
  scale = Math.max(planLimits.minScale, Math.min(planLimits.maxScale, scale));
  const world = planToWorld(point, view, anchor);
  const center = world.map((value, i) => value - (point[i] - anchor[i]) / scale);
  return { center: constrainToBoundary(center, boundary), scale };
}
export function panPlan(view, delta, boundary) {
  return { ...view, center: constrainToBoundary(view.center.map((value, i) => value - delta[i] / view.scale), boundary) };
}
export function pinchPlan(view, before, after, anchor, boundary) {
  const midpoint = points => points[0].map((value, i) => (value + points[1][i]) / 2);
  const distance = points => Math.hypot(...points[0].map((value, i) => value - points[1][i]));
  const from = midpoint(before), to = midpoint(after);
  const zoomed = zoomPlan(view, view.scale * distance(after) / Math.max(1, distance(before)), from, anchor, boundary);
  return panPlan(zoomed, to.map((value, i) => value - from[i]), boundary);
}
export function planBounds(points) {
  return { left: Math.min(...points.map(p => p[0])), right: Math.max(...points.map(p => p[0])),
    top: Math.min(...points.map(p => p[1])), bottom: Math.max(...points.map(p => p[1])) };
}
export function intersectsPlan(a, b, padding = 0) {
  return a.left - padding < b.right && a.right + padding > b.left && a.top - padding < b.bottom && a.bottom + padding > b.top;
}
export function pickPlanBuilding(point, buildings) {
  return [...buildings].reverse().find(building => insideFootprint(point, building))?.id || null;
}
export function planScaleBar(scale) {
  const meters = [20, 50, 100, 200, 500].filter(value => value * scale <= 90).at(-1) || 20;
  return { meters, pixels: meters * scale };
}
