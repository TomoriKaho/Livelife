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
// 黄色屋顶在默认俯视距离只有十几至几十像素宽。单靠亚像素纸齿
// 会被 Canvas 缩小采样平均成纯色，所以另加可辨识的宽笔触与渐尖露纸。
const yellowColors = new Set(['#ffd600', '#ffdf16', '#ffe93d', '#fbd21a', '#ffdf32']);
function yellowShading(painter, size) {
  const colors = ['#ffd600', '#ffdf16', '#ffe93d', '#fbd21a'];
  const point = (along, across) => [along * .8660254 + across * .5, -along * .5 + across * .8660254];
  painter.lineCap = painter.lineJoin = 'round';
  for (let lane = 0, row = 0; row < size * 1.37; lane++, row += 9) {
    for (let step = 0, start = -size * .5; start < size * .87; step++) {
      const length = 32 + hash(lane, step) * 48;
      const a = point(start, row), b = point(start + length / 2, row + 1), c = point(start + length, row);
      painter.strokeStyle = colors[Math.floor(hash(lane + 71, step) * colors.length)];
      painter.globalAlpha = .2 + hash(lane + 19, step) * .24;
      painter.lineWidth = 12 + hash(lane + 43, step) * 5;
      painter.beginPath(); painter.moveTo(...a); painter.quadraticCurveTo(...b, ...c); painter.stroke();
      start += length - 8;
    }
  }
  painter.fillStyle = '#fffaf0';
  for (let lane = 0, row = 3; row < size * 1.37; lane++, row += 14) {
    for (let step = 0, start = -size * .5 + hash(lane, 107) * 30; start < size * .87; step++) {
      const length = 14 + hash(lane + 101, step) * 24;
      const thickness = .9 + hash(lane + 127, step) * 1.5;
      const edgeA = [], edgeB = [];
      for (let i = 0; i <= 8; i++) {
        const t = i / 8, middle = row + Math.sin(t * Math.PI) * .65;
        const half = Math.sin(t * Math.PI) * thickness / 2;
        edgeA.push(point(start + t * length, middle + half));
        edgeB.push(point(start + t * length, middle - half));
      }
      painter.globalAlpha = .55 + hash(lane + 151, step) * .25;
      painter.beginPath(); painter.moveTo(...edgeA[0]);
      [...edgeA.slice(1), ...edgeB.reverse()].forEach(p => painter.lineTo(...p));
      painter.closePath(); painter.fill();
      start += length + 18 + hash(lane + 173, step) * 28;
    }
  }
  painter.globalAlpha = 1;
  // 最后一层纸齿也覆盖搭接笔触和露纸，避免笔触像光滑的矢量条带。
  const pixels = painter.getImageData(0, 0, size, size);
  for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
    const grain = (hash(x + 317, y + 211) - .5) * .18;
    for (let c = 0; c < 3; c++) {
      const i = (y * size + x) * 4 + c;
      pixels.data[i] += (255 - pixels.data[i]) * grain;
    }
  }
  painter.putImageData(pixels, 0, 0);
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
    const yellow = yellowColors.has(color.toLowerCase());
    if (yellow) yellowShading(painter, size);
    const pattern = context.createPattern(tile, 'repeat');
    // 黄屋顶的纹理块约 256m，默认视角笔触约 5–10px、露纸约 1px。
    // 其余地景维持原来的 77m 纹理块，不增加地图背景的视觉噪声。
    pattern.setTransform(new DOMMatrix().scale(yellow ? 1 : .3));
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
