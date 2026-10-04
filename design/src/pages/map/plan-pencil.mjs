// Canvas 地图的色面纹理：固定种子、宽笔触平涂、-30° 同向露纸。
// 纹理固定在地图米制坐标中，拖动和缩放不会重新随机上色。
const hash = (x, y) => {
  let n = Math.imul(x, 374761393) + Math.imul(y, 668265263);
  n = Math.imul(n ^ (n >>> 13), 1274126177);
  return ((n ^ (n >>> 16)) >>> 0) / 4294967296;
};
function noise(x, y) {
  const i = Math.floor(x), j = Math.floor(y), fx = x - i, fy = y - j;
  const u = fx * fx * (3 - 2 * fx), v = fy * fy * (3 - 2 * fy);
  const mix = (a, b, t) => a + (b - a) * t;
  return mix(mix(hash(i, j), hash(i + 1, j), u), mix(hash(i, j + 1), hash(i + 1, j + 1), u), v);
}
export function createPlanPatterns(context, colors) {
  const size = 256, pressure = new Float32Array(size * size);
  for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
    const along = x * .8660254 - y * .5, across = x * .5 + y * .8660254;
    const broad = noise(along * .012, across * .11) - .5;
    const overlap = noise(along * .025 + 17, across * .19) - .5;
    const gap = Math.max(0, Math.sin(across * .31 + .1 * Math.sin(along * .04))) ** 26
      * Math.max(0, noise(along * .035, Math.floor(across * .08)) - .4);
    pressure[y * size + x] = Math.max(.02, Math.min(.35, .07 + broad * .16 + overlap * .07 + (hash(x, y) - .5) * .075 + gap * .42));
  }
  return Object.fromEntries([...new Set(colors)].map(color => {
    const tile = document.createElement('canvas'); tile.width = tile.height = size;
    const painter = tile.getContext('2d'), pixels = painter.createImageData(size, size);
    const pigment = color.match(/[a-f0-9]{2}/gi).map(value => parseInt(value, 16)), paper = [255, 250, 240];
    for (let i = 0; i < pressure.length; i++) {
      for (let c = 0; c < 3; c++) pixels.data[i * 4 + c] = Math.round(pigment[c] + (paper[c] - pigment[c]) * pressure[i]);
      pixels.data[i * 4 + 3] = 255;
    }
    painter.putImageData(pixels, 0, 0);
    const pattern = context.createPattern(tile, 'repeat');
    pattern.setTransform(new DOMMatrix().scale(.3)); // 纹理块约 77m，近景仍保留纸齿。
    return [color, pattern];
  }));
}
export function pencilPlanPath(points, holes = []) {
  const path = new Path2D();
  for (const ring of [points, ...holes]) {
    if (!ring.length) continue;
    path.moveTo(...ring[0]);
    for (let i = 1; i <= ring.length; i++) {
      const a = ring[i - 1], b = ring[i % ring.length], length = Math.hypot(b[0] - a[0], b[1] - a[1]);
      if (!length) continue;
      const wobble = Math.sin(a[0] * .13 + a[1] * .17 + i) * Math.min(.18, length * .008);
      path.quadraticCurveTo((a[0] + b[0]) / 2 - (b[1] - a[1]) / length * wobble,
        (a[1] + b[1]) / 2 + (b[0] - a[0]) / length * wobble, ...b);
    }
    path.closePath();
  }
  return path;
}
