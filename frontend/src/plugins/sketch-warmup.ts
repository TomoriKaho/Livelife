import { createApp, nextTick, type Component, type InjectionKey } from 'vue';
import { createMemoryHistory, createRouter, type RouteRecordRaw } from 'vue-router';
import { createSketchPlugin } from './sketch.js';
import type { createSketchBitmapQueue } from './sketch-bitmap';

export const sketchWarmupKey: InjectionKey<boolean> = Symbol('sketch-warmup');
type WarmupScenario = () => void | Promise<void>;
export const sketchWarmupScenariosKey: InjectionKey<(scenarios: WarmupScenario[]) => () => void>
  = Symbol('sketch-warmup-scenarios');

export async function waitSketchFont() {
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    await Promise.race([
      document.fonts.load('16px "LiveLife Rounded"').catch(() => []),
      new Promise(resolve => { timer = setTimeout(resolve, 1500); }),
    ]);
  } finally { if (timer) clearTimeout(timer); }
}

// Render only page layouts in an isolated memory router. No visible navigation,
// native back listener, or 3D scene is started during this preparation step.
export async function warmSketchLayouts(root: Component, routes: readonly RouteRecordRaw[],
  bitmaps: ReturnType<typeof createSketchBitmapQueue>) {
  const deadline = performance.now() + 30000;
  const status = document.createElement('div');
  status.setAttribute('role', 'status');
  status.textContent = '正在准备界面…';
  status.style.cssText = 'position:fixed;inset:0;display:grid;place-items:center;background:#f8f4ea;color:#20304b;font:16px sans-serif';
  document.body.append(status);
  const host = document.createElement('div');
  host.inert = true;
  host.setAttribute('aria-hidden', 'true');
  const top = Number.parseFloat(getComputedStyle(document.body).paddingTop) || 0;
  host.style.cssText = `position:fixed;left:-10000px;top:${top}px;width:100%;visibility:hidden;pointer-events:none`;
  document.body.append(host);
  let app: ReturnType<typeof createApp> | undefined;
  let complete = true;
  let pageScenarios: WarmupScenario[] = [];
  const frame = () => new Promise<void>(resolve => requestAnimationFrame(() => resolve()));
  async function withinBudget(task: Promise<unknown>, limit = deadline - performance.now()) {
    let timer: ReturnType<typeof setTimeout> | undefined;
    try {
      return await Promise.race([
        task.then(() => true),
        new Promise<boolean>(resolve => { timer = setTimeout(() => resolve(false), Math.max(0, limit)); }),
      ]);
    } finally { if (timer) clearTimeout(timer); }
  }
  try {
    const memoryRouter = createRouter({ history: createMemoryHistory(), routes });
    const pages = ['/onboarding', '/detail', '/calendar', '/interests', '/agent', '/map', '/more'];
    await memoryRouter.push(pages[0]!);
    app = createApp(root, { warming: true }).provide(sketchWarmupKey, true)
      .provide(sketchWarmupScenariosKey, scenarios => {
        pageScenarios = scenarios;
        return () => { if (pageScenarios === scenarios) pageScenarios = []; };
      })
      .use(memoryRouter).use(createSketchPlugin(bitmaps));
    app.mount(host);
    for (const [index, page] of pages.entries()) {
      if (performance.now() >= deadline) { complete = false; break; }
      status.textContent = `正在准备界面（${index + 1}/${pages.length}）…`;
      await memoryRouter.push(page);
      await nextTick();
      await frame();
      await frame();
      if (!await withinBudget(bitmaps.whenIdle())) { complete = false; break; }
      await frame();
      const scenarios = [...pageScenarios];
      for (const [subIndex, prepare] of scenarios.entries()) {
        if (performance.now() >= deadline) { complete = false; break; }
        status.textContent = `正在准备界面（${index + 1}/${pages.length} · 子页面 ${subIndex + 1}/${scenarios.length}）…`;
        if (!await withinBudget(Promise.resolve().then(prepare))) { complete = false; break; }
        await nextTick(); await frame(); await frame();
        if (!await withinBudget(bitmaps.whenIdle())) { complete = false; break; }
        await frame();
      }
    }
  } catch (error) {
    complete = false;
    console.warn('界面预热未完成，继续启动。', error);
  } finally {
    app?.unmount();
    host.remove();
    status.remove();
  }
  return complete;
}
