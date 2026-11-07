// From the Vite development page Console (scripts are not bundled in the APK):
// await (await import('/scripts/static-sketch.browser.mjs')).verifyStaticSketchGeometry()
import { createStaticSketchRenderer } from '../src/plugins/static-sketch.ts';

export async function verifyStaticSketchGeometry() {
  const results = [], renderer = createStaticSketchRenderer();
  const root = document.createElement('div');
  root.style.cssText = 'position:fixed;left:-10000px;top:0';
  root.setAttribute('aria-hidden', 'true'); document.body.append(root);
  try {
    for (const [width, height] of [[24,24], [160,24], [160,32], [39,39], [160,40], [64,64], [160,180]]) {
      const control = document.createElement('div');
      control.className = 'sketch sketch-white'; control.dataset.pencil = 'blue';
      control.style.cssText = `position:relative;width:${width}px;height:${height}px`;
      root.append(control); renderer.update(control);
      await new Promise(resolve => requestAnimationFrame(resolve));
      const layer = control.querySelector('.sketch-decoration');
      const bounds = layer.getBoundingClientRect();
      const frame = getComputedStyle(layer, '::after'), fill = getComputedStyle(layer, '::before');
      const frameHeight = parseFloat(frame.height) + parseFloat(frame.borderTopWidth) + parseFloat(frame.borderBottomWidth);
      const frameWidth = parseFloat(frame.width) + parseFloat(frame.borderLeftWidth) + parseFloat(frame.borderRightWidth);
      if (Math.abs(frameHeight - bounds.height) > .5 || Math.abs(frameWidth - bounds.width) > .5)
        throw new Error(`${width}x${height}: border box extends beyond decoration layer`);
      const scale = Math.min(1, bounds.width / 40, bounds.height / 40);
      if (Math.abs(parseFloat(fill.top) - 4 * scale) > .5)
        throw new Error(`${width}x${height}: fill and frame use different corner scales`);
      if (frame.borderImageSource === 'none' || fill.backgroundImage === 'none')
        throw new Error(`${width}x${height}: decorations disappeared`);
      results.push(`${width}x${height}: frame bounds and fill scale aligned`);
      renderer.release(control); control.remove();
    }
    return results;
  } finally { root.remove(); }
}
