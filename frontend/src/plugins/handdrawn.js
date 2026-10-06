/*
 * 本地 SVG 手绘渲染器：轮廓在真实像素坐标中采样，尺寸变化时重画。
 * 彩铅由宽笔触交叠平涂与纸齿透明度组成；SVG 底面透明。
 * 固定随机种子保证同一控件不会在导航或刷新时改变笔迹。
 */
export function createHandDrawnRenderer() {
  const NS = 'http://www.w3.org/2000/svg';
  const palettes = {
    yellow: ['#ffd600', '#ffdf16', '#ffe93d', '#fbd21a'],
    blue: ['#5ea7e5', '#78b8ed', '#a3d1f5', '#4f95d2'],
    mint: ['#88cbb2', '#a6e3c5', '#d0f1de', '#78bd9f'],
    pink: ['#e99796', '#f7b4ae', '#ffd6ca', '#dc8289'],
    lavender: ['#ab94de', '#c4afea', '#e4d6ff', '#997fcb'],
  };
  let nextId = 0;
  const drawings = new WeakMap();
  const tracked = new Set();

  function random(seed) {
    let value = seed >>> 0;
    return () => {
      value = (Math.imul(value, 1664525) + 1013904223) >>> 0;
      return value / 4294967296;
    };
  }
  const num = value => value.toFixed(2);
  function node(tag, attributes = {}) {
    const element = document.createElementNS(NS, tag);
    Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, value));
    return element;
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

  // 底部栏只勾上沿，两端以圆角落到手机边缘，中间保持平直。
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

  // 颜料和漏色共用 -30° 的涂抹坐标，保证纹理跟随同一宽笔触方向。
  function pencilSpace(width, height) {
    const cos = Math.cos(-Math.PI / 6), sin = Math.sin(-Math.PI / 6);
    return {
      alongMin: height * sin - 20, alongMax: width * cos + 20,
      acrossMax: -width * sin + height * cos + 20,
      point: (along, across) => [along * cos - across * sin, along * sin + across * cos],
    };
  }

  function pencilShading(width, height, seed, colors) {
    const rng = random(seed * 37);
    const group = node('g', { 'stroke-linecap': 'round' });
    // 连续的浅颜料层也经过纸齿滤镜，不构成不透明背景色块。
    group.append(node('rect', { width, height, fill: colors[2], opacity: colors === palettes.yellow ? '.72' : '.54' }));
    const space = pencilSpace(width, height);
    // 同向宽笔触密集叠涂，色面连续，局部压力变化顺着涂抹方向展开。
    for (let pass = 0; pass < 2; pass++) {
      for (let row = -14 + pass * 2; row < space.acrossMax; row += 4.5 + rng() * .8) {
        let start = space.alongMin - rng() * 25;
        while (start < space.alongMax) {
          const length = 30 + rng() * 55;
          const center = start + length / 2;
          const pressure = .72 + .23 * Math.sin(center / 48 + row / 17 + seed) + .17 * Math.sin(center / 87 - row / 29);
          const points = [];
          for (let i = 0; i <= 5; i++) {
            const along = start + length * i / 5;
            const across = row + Math.sin(along / 22 + seed) * 1.3 + (rng() - .5) * .6;
            points.push(space.point(along, across));
          }
          group.append(node('path', {
            d: pathFor(points, false, true),
            fill: 'none',
            stroke: colors[Math.floor(rng() * colors.length)],
            'stroke-width': num(12 + rng() * 6),
            opacity: num((.11 + rng() * .12) * pressure),
          }));
          start += length - 8;
        }
      }
    }
    // 纸齿通过后续透明度滤镜实现，不额外叠加白色或纸色斑点。
    return group;
  }

  function draw(element) {
    const record = drawings.get(element);
    const width = element.clientWidth, height = element.clientHeight;
    if (!record || width < 8 || height < 8) return;
    const color = element.dataset.pencil || '';
    const isBottomNav = element.classList.contains('bottom-nav');
    const whiteCard = element.classList.contains('sketch-white') && !palettes[color];
    const fillOnly = element.classList.contains('sketch-fill-only');
    const castColors = { yellow: '#ffdf32', blue: '#9ac8f2', mint: '#7ec9a8', pink: '#f4b2ab', lavender: '#c9b6f0' };
    const castName = element.dataset.cast || color;
    const cast = element.classList.contains('sketch-cast') ? (castColors[castName] || '#9ac8f2') : '';
    const active = isBottomNav ? element.querySelector('[aria-current="page"]') : null;
    const current = `${width}:${height}:${color}:${whiteCard ? 'white' : ''}:${fillOnly ? 'fill' : ''}:${cast}:${active?.dataset.nav || ''}`;
    if (record.current === current) return;
    record.current = current;
    const { svg, seed } = record;
    svg.replaceChildren();
    svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
    const outline = isBottomNav ? topEdge(width, seed) : perimeter(width, height, seed);
    const defs = node('defs');
    const clip = node('clipPath', { id: `pencil-clip-${seed}` });
    const fillPath = isBottomNav
      ? `${pathFor(outline, false, true)} L${width} ${height} L0 ${height} Z`
      : pathFor(outline, true, true);
    clip.append(node('path', { d: fillPath }));
    defs.append(clip);
    // 纸纹让颜料在像素尺度上断续附着，避免笔触呈现光滑的矢量色带。
    const pigment = node('filter', { id: `pencil-pigment-${seed}`, x: '0%', y: '0%', width: '100%', height: '100%', 'color-interpolation-filters': 'sRGB' });
    pigment.append(node('feTurbulence', { type: 'fractalNoise', baseFrequency: '.85', numOctaves: '3', seed, result: 'paperTooth' }));
    pigment.append(node('feColorMatrix', { in: 'paperTooth', type: 'matrix', values: '0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  .28 .53 .19 0 0' }));
    const pressure = node('feComponentTransfer', { result: 'paperCoverage' });
    pressure.append(node('feFuncA', { type: 'linear', slope: '2.6', intercept: color === 'yellow' ? '-.38' : '-.5' }));
    pigment.append(pressure);
    pigment.append(node('feComposite', { in: 'SourceGraphic', in2: 'paperCoverage', operator: 'in' }));
    defs.append(pigment);
    svg.append(defs);
    // 白底裁在同一条勾线内，避免在轮廓外垫一个直角矩形。
    if (whiteCard) svg.append(node('path', { d: fillPath, fill: '#fff' }));
    if (palettes[color]) {
      const fill = node('g', { 'clip-path': `url(#pencil-clip-${seed})` });
      // 选中按钮底面透明：从黄色导航笔触中让出蓝色按钮的区域，避免混色。
      if (active) {
        const mask = node('mask', { id: `pencil-nav-mask-${seed}`, maskUnits: 'userSpaceOnUse', x: 0, y: 0, width, height });
        mask.append(node('rect', { width, height, fill: 'white' }));
        const activeOutline = perimeter(active.clientWidth, active.clientHeight, drawings.get(active).seed);
        mask.append(node('path', { d: pathFor(activeOutline, true, true), fill: 'black', transform: `translate(${active.offsetLeft + active.clientLeft} ${active.offsetTop + active.clientTop})` }));
        defs.append(mask);
        fill.setAttribute('mask', `url(#pencil-nav-mask-${seed})`);
      }
      const strokes = pencilShading(width, height, seed, palettes[color]);
      strokes.setAttribute('filter', `url(#pencil-pigment-${seed})`);
      // 漏色沿斜向笔触的相接处出现，长短与宽度变化，但不再随机散成斑点。
      const wear = node('mask', { id: `pencil-wear-${seed}`, maskUnits: 'userSpaceOnUse', x: 0, y: 0, width, height });
      wear.append(node('rect', { width, height, fill: 'white' }));
      const wearRng = random(seed * 59);
      const space = pencilSpace(width, height);
      for (let lane = 0; lane < space.acrossMax; lane += 12 + wearRng() * 2) {
        let along = space.alongMin + wearRng() * 35;
        while (along < space.alongMax) {
          const length = 18 + wearRng() * 20;
          const thickness = 1 + wearRng() * 2;
          const edgeA = [], edgeB = [];
          for (let i = 0; i <= 8; i++) {
            const t = i / 8;
            const center = lane + Math.sin(t * Math.PI) * .6;
            const halfWidth = Math.sin(t * Math.PI) * thickness / 2 * (.8 + wearRng() * .4);
            edgeA.push(space.point(along + t * length, center + halfWidth));
            edgeB.push(space.point(along + t * length, center - halfWidth));
          }
          wear.append(node('path', { d: pathFor([...edgeA, ...edgeB.reverse()], true, true), fill: 'black', opacity: num(.55 + wearRng() * .3) }));
          along += length + 18 + wearRng() * 40;
        }
      }
      defs.append(wear);
      strokes.setAttribute('mask', `url(#pencil-wear-${seed})`);
      fill.append(strokes);
      svg.append(fill);
    }
    const faint = element.classList.contains('page-outlet');
    const ink = faint ? '#7f91a3' : '#20304b';
    // 偏移笔迹只沿右缘和底缘，在转入左边框之前停下。
    const accent = cast || (element.classList.contains('art-paper') ? '#9ac8f2' : '#ffdf32');
    const highlighted = Boolean(cast) || element.matches('.brand, .art-paper') || (element.classList.contains('nav-item') && element.hasAttribute('aria-current'));
    if (highlighted) {
      const leftX = Math.max(18, Math.min(40, width * 0.18));
      let end = outline.length;
      for (let i = 6; i < outline.length; i++) {
        if (outline[i][0] < leftX) { end = i; break; }
      }
      svg.append(node('path', { d: pathFor(outline.slice(0, Math.max(4, end)), false, true), fill: 'none', stroke: accent, 'stroke-width': '3.6', opacity: '.72', transform: 'translate(2 3)', 'stroke-linecap': 'round' }));
    }
    if (fillOnly) return;
    // 主导航沿用参考图的视觉层级：只勾出当前项，其他入口保留图标和文字。
    if (element.classList.contains('nav-item') && !element.hasAttribute('aria-current')) return;
    // 主勾线、偏移复描，以及深浅不同的短线段共同形成石墨轮廓。
    svg.append(node('path', { d: pathFor(outline, !isBottomNav, true), fill: 'none', stroke: ink, 'stroke-width': faint ? '.85' : '1.65', opacity: faint ? '.4' : '.92', 'stroke-linejoin': 'round' }));
    const retrace = isBottomNav ? topEdge(width, seed, 1) : perimeter(width, height, seed, 1);
    svg.append(node('path', { d: pathFor(retrace, !isBottomNav, true), fill: 'none', stroke: ink, 'stroke-width': '.65', opacity: faint ? '.24' : '.54', 'stroke-linejoin': 'round' }));
    if (!faint) {
      const rng = random(seed * 83);
      for (let i = 0; i < outline.length - 3; i += 3 + Math.floor(rng() * 4)) {
        svg.append(node('path', { d: pathFor(outline.slice(i, i + 3 + Math.floor(rng() * 3)), false, true), fill: 'none', stroke: ink, 'stroke-width': num(.6 + rng() * .9), opacity: num(.2 + rng() * .55), 'stroke-linecap': 'round' }));
      }
    }
  }

  const observer = new ResizeObserver(entries => entries.forEach(({ target }) => draw(target)));
  function release(element) {
    const record = drawings.get(element);
    if (!record) return;
    observer.unobserve(element);
    record.svg.remove();
    element.classList.remove('has-sketch');
    drawings.delete(element);
    tracked.delete(element);
  }
  function refresh() {
    tracked.forEach(element => { if (!element.isConnected) release(element); });
    const elements = document.querySelectorAll('.sketch, .nav-item, .bottom-nav, .page-outlet, .icon-button:not(.notification-button)');
    elements.forEach(element => {
      if (!drawings.has(element)) {
        const svg = node('svg', { class: 'sketch-render', 'aria-hidden': 'true', focusable: 'false', preserveAspectRatio: 'none' });
        element.prepend(svg);
        drawings.set(element, { svg, seed: ++nextId * 127, current: '' });
        tracked.add(element);
        observer.observe(element);
      }
      // Vue/RouterLink 可能重写 class 或内容，恢复装饰层而不更换笔迹种子。
      element.classList.add('has-sketch');
      const { svg } = drawings.get(element);
      if (svg.parentNode !== element) element.prepend(svg);
    });
    elements.forEach(draw);
  }
  function dispose() {
    tracked.forEach(release);
    observer.disconnect();
  }
  return { refresh, release, dispose };
}
