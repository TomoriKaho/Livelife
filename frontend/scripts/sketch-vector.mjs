// Build-time only. Pencil algorithms migrated from src/plugins/handdrawn.js.
// No browser APIs or runtime imports: the client ships only the rendered PNGs.
class SvgNode {
  constructor(tag, attributes = {}) { this.tag = tag; this.attributes = attributes; this.children = []; }
  setAttribute(key, value) { this.attributes[key] = value; }
  append(...children) { this.children.push(...children); }
  toString() {
    const escape = value => String(value).replaceAll('&', '&amp;').replaceAll('"', '&quot;').replaceAll('<', '&lt;');
    return `<${this.tag} ${Object.entries(this.attributes).map(([key,value]) => `${key}="${escape(value)}"`).join(' ')}>${this.children.join('')}</${this.tag}>`;
  }
}
function random(seed) {
  let value = seed >>> 0;
  return () => {
    value = (Math.imul(value, 1664525) + 1013904223) >>> 0;
    return value / 4294967296;
  };
}
const num = value => value.toFixed(2);
function node(tag, attributes = {}) {
  return new SvgNode(tag, attributes);
}

// 手绘勾线保留圆角；背景透明，不通过 CSS 圆角色块构造按钮。
function perimeter(width, height, seed, pass = 0) {
  const rng = random(seed + pass * 719);
  const inset = 4;
  const radius = Math.min(15, height / 3, width / 4);
  const corners = [
    [width - inset - radius, inset + radius, -Math.PI / 2],
    [width - inset - radius, height - inset - radius, 0],
    [inset + radius, height - inset - radius, Math.PI / 2],
    [inset + radius, inset + radius, Math.PI],
  ];
  const ideal = [];
  corners.forEach(([cx, cy, start], index) => {
    for (let i = 0; i <= 9; i++) {
      const angle = start + i / 9 * Math.PI / 2;
      ideal.push([cx + radius * Math.cos(angle), cy + radius * Math.sin(angle)]);
    }
    const [nx, ny, angle] = corners[(index + 1) % 4];
    const from = ideal[ideal.length - 1];
    const to = [nx + radius * Math.cos(angle), ny + radius * Math.sin(angle)];
    const steps = Math.ceil(Math.hypot(to[0] - from[0], to[1] - from[1]) / 5);
    for (let i = 1; i < steps; i++) ideal.push([from[0] + (to[0] - from[0]) * i / steps, from[1] + (to[1] - from[1]) * i / steps]);
  });
  return ideal.map(([x, y], i) => {
    const drift = Math.sin(i * .34 + seed) * .6;
    return [x + drift + (rng() - .5) * .45 + pass * .2, y + Math.sin(i * .27 + seed * .7) * .55 + (rng() - .5) * .4 - pass * .16];
  });
}
function pathFor(points, close = true, smooth = false) {
  if (smooth && points.length > 2) {
    const midpoint = (a, b) => [num((a[0] + b[0]) / 2), num((a[1] + b[1]) / 2)].join(' ');
    let path = close ? `M${midpoint(points[points.length - 1], points[0])}` : `M${points[0].map(num).join(' ')} L${midpoint(points[0], points[1])}`;
    for (let i = close ? 0 : 1; i < points.length - (close ? 0 : 1); i++) {
      path += ` Q${points[i].map(num).join(' ')} ${midpoint(points[i], points[(i + 1) % points.length])}`;
    }
    return path + (close ? ' Z' : ` L${points[points.length - 1].map(num).join(' ')}`);
  }
  return points.map(([x, y], i) => `${i ? 'L' : 'M'}${num(x)} ${num(y)}`).join(' ') + (close ? ' Z' : '');
}


export function sketchVector({ cast = '', width = 96, height = 96, seed = 127 } = {}) {
  const svg = node('svg', { xmlns: 'http://www.w3.org/2000/svg', width, height, viewBox: `0 0 ${width} ${height}` });
  const outline = perimeter(width, height, seed);
  if (cast) svg.append(node('path', { d: pathFor(outline.slice(0, 36), false, true), fill: 'none', stroke: cast, 'stroke-width': '3.6', opacity: '.72', transform: 'translate(2 3)', 'stroke-linecap': 'round' }));
  svg.append(node('path', { d: pathFor(outline, true, true), fill: 'none', stroke: '#20304b', 'stroke-width': '1.65', opacity: '.92', 'stroke-linejoin': 'round' }));
  svg.append(node('path', { d: pathFor(perimeter(width, height, seed, 1), true, true), fill: 'none', stroke: '#20304b', 'stroke-width': '.65', opacity: '.54', 'stroke-linejoin': 'round' }));
  return svg;
}

function topEdge(width, seed, pass = 0) {
  const rng = random(seed + pass * 719);
  const radius = Math.min(14, width / 8);
  const top = 2.5 - pass * .16;
  const points = [];
  for (let i = 0; i <= 9; i++) {
    const angle = i / 9 * Math.PI / 2;
    points.push([radius - radius * Math.cos(angle), top + radius - radius * Math.sin(angle)]);
  }
  const steps = Math.ceil((width - radius * 2) / 5);
  for (let i = 1; i < steps; i++) {
    const envelope = Math.sin(Math.PI * i / steps);
    points.push([
      radius + (width - radius * 2) * i / steps,
      top + envelope * (Math.sin(i * .3 + seed) * .35 + (rng() - .5) * .3),
    ]);
  }
  for (let i = 0; i <= 9; i++) {
    const angle = i / 9 * Math.PI / 2;
    points.push([width - radius + radius * Math.sin(angle), top + radius - radius * Math.cos(angle)]);
  }
  return points;
}

export function navigationVector({ width = 96, height = 48, seed = 127 } = {}) {
  const svg = node('svg', { xmlns: 'http://www.w3.org/2000/svg', width, height, viewBox: `0 0 ${width} ${height}` });
  for (const [pass, strokeWidth, opacity] of [[0, 1.65, .92], [1, .65, .54]]) {
    svg.append(node('path', { d: pathFor(topEdge(width, seed, pass), false, true), fill: 'none', stroke: '#20304b', 'stroke-width': strokeWidth, opacity, 'stroke-linejoin': 'round' }));
  }
  return svg;
}
