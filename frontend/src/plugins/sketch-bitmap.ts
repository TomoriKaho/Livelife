// Complex SVG filters are evaluated off the live DOM, once per drawing.
// Scrolling pages display reusable transparent PNGs instead of SVG filters.
export function createSketchBitmapQueue() {
  type Bitmap = { image: HTMLImageElement; url: string; pixels: number; refs: number };
  type Job = { cancelled: boolean; run: () => Promise<void> };
  const jobs: Job[] = [];
  const ready: Array<() => void> = [];
  const cache = new Map<string, Bitmap>();
  const identities = new Map<string, string>();
  const idle: Array<() => void> = [];
  let busy = false, pixelsInUse = 0;
  const maxPixels = 32 * 1024 * 1024;
  const padding = 6; // Include the pencil outline displaced outside the box.

  function evict(required: number) {
    for (const [key, bitmap] of cache) {
      if (pixelsInUse + required <= maxPixels && cache.size < 512) break;
      if (bitmap.refs) continue;
      cache.delete(key);
      for (const [identity, target] of identities) if (target === key) identities.delete(identity);
      URL.revokeObjectURL(bitmap.url);
      pixelsInUse -= bitmap.pixels;
    }
  }
  async function drain() {
    if (busy) return;
    busy = true;
    try {
      while (jobs.length) {
        const job = jobs.shift()!;
        if (!job.cancelled) await job.run();
      }
    } finally {
      busy = false;
      // Publish a cold batch together instead of revealing each decoration.
      ready.splice(0).forEach(publish => publish());
      idle.splice(0).forEach(resolve => resolve());
    }
  }

  function render(svg: SVGSVGElement, width: number, height: number,
    publish: (image: HTMLImageElement, release: () => void) => void, identity?: string) {
    const clone = svg.cloneNode(true) as SVGSVGElement;
    clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
    clone.setAttribute('width', String(width + padding * 2));
    clone.setAttribute('height', String(height + padding * 2));
    clone.setAttribute('viewBox', `-${padding} -${padding} ${width + padding * 2} ${height + padding * 2}`);
    const source = new XMLSerializer().serializeToString(clone);
    const key = `${window.devicePixelRatio}:${source}`;
    let held: Bitmap | undefined, published = false;
    const release = () => { if (held) { held.refs--; held = undefined; } };
    function retain(bitmap: Bitmap) {
      held = bitmap;
      bitmap.refs++;
      cache.delete(key);
      cache.set(key, bitmap);
      if (identity) identities.set(identity, key);
    }
    function display() {
      if (job.cancelled) { release(); return; }
      const image = held!.image.cloneNode() as HTMLImageElement;
      published = true;
      publish(image, release);
    }
    const job: Job = {
      cancelled: false,
      async run() {
        let sourceUrl = '', bitmapUrl = '', reserved = 0;
        try {
          const existing = cache.get(key);
          if (existing) { retain(existing); ready.push(display); return; }
          const area = (width + padding * 2) * (height + padding * 2);
          let ratio = Math.min(window.devicePixelRatio || 1, 3, Math.sqrt(4 * 1024 * 1024 / area));
          evict(Math.ceil(area * ratio * ratio) + 8192);
          ratio = Math.min(ratio, Math.sqrt(Math.max(0, maxPixels - pixelsInUse - 8192) / area));
          if (ratio < .5) return;
          const canvas = document.createElement('canvas');
          canvas.width = Math.ceil((width + padding * 2) * ratio);
          canvas.height = Math.ceil((height + padding * 2) * ratio);
          reserved = canvas.width * canvas.height;
          pixelsInUse += reserved;
          sourceUrl = URL.createObjectURL(new Blob([source], { type: 'image/svg+xml' }));
          const input = new Image();
          input.src = sourceUrl;
          await input.decode();
          if (job.cancelled) return;
          const context = canvas.getContext('2d');
          if (!context) throw new Error('Canvas 2D unavailable');
          context.drawImage(input, 0, 0, canvas.width, canvas.height);
          const blob = await new Promise<Blob>((resolve, reject) => {
            canvas.toBlob(result => result ? resolve(result) : reject(new Error('PNG encoding failed')), 'image/png');
          });
          if (job.cancelled) return;
          bitmapUrl = URL.createObjectURL(blob);
          const image = new Image();
          image.src = bitmapUrl;
          await image.decode();
          if (job.cancelled) return;
          image.className = 'sketch-render sketch-bitmap';
          image.alt = '';
          image.setAttribute('aria-hidden', 'true');
          image.draggable = false;
          image.style.cssText = `left:-${padding}px;top:-${padding}px;width:calc(100% + ${padding * 2}px);height:calc(100% + ${padding * 2}px)`;
          retain({ image, url: bitmapUrl, pixels: reserved, refs: 0 });
          bitmapUrl = '';
          reserved = 0; // The cache now owns these pixels and the PNG URL.
          ready.push(display);
        } catch (error) {
          if (!job.cancelled) console.warn('手绘装饰生成失败，保留页面内容。', error);
        } finally {
          if (sourceUrl) URL.revokeObjectURL(sourceUrl);
          if (bitmapUrl) URL.revokeObjectURL(bitmapUrl);
          pixelsInUse -= reserved;
        }
      },
    };
    const existing = cache.get(key);
    if (existing) { retain(existing); display(); }
    else { jobs.push(job); void drain(); }
    return () => { job.cancelled = true; if (!published) release(); };
  }
  function reuse(identity: string, publish: (image: HTMLImageElement, release: () => void) => void) {
    const key = identities.get(identity), bitmap = key ? cache.get(key) : undefined;
    if (!key || !bitmap) return undefined;
    cache.delete(key); cache.set(key, bitmap);
    bitmap.refs++;
    let held = true;
    publish(bitmap.image.cloneNode() as HTMLImageElement, () => { if (held) { held = false; bitmap.refs--; } });
    return () => {};
  }
  function dispose() {
    jobs.forEach(job => { job.cancelled = true; });
    jobs.length = 0;
    for (const bitmap of cache.values()) URL.revokeObjectURL(bitmap.url);
    cache.clear();
    identities.clear();
    // Active jobs are cancelled by their owner's release before disposal.
  }
  function whenIdle() {
    return busy ? new Promise<void>(resolve => idle.push(resolve)) : Promise.resolve();
  }
  return { render, reuse, dispose, whenIdle };
}
