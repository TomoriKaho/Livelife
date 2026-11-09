// In a Vite page with the bottom navigation visible:
// await (await import('/scripts/viewport-scroll.browser.mjs')).verifyViewportScroll()
export async function verifyViewportScroll() {
  const root = document.documentElement, main = document.querySelector('.page-main');
  const nav = document.querySelector('.bottom-nav');
  if (!main || !nav) throw new Error('Open a page with bottom navigation first');
  const properties = ['--safe-area-inset-top', '--safe-area-inset-bottom'];
  const saved = properties.map(name => [root.style.getPropertyValue(name), root.style.getPropertyPriority(name)]);
  const originalScroll = main.scrollTop;
  const probe = document.createElement('div');
  probe.style.cssText = 'height:2000px;flex:0 0 2000px';
  probe.setAttribute('aria-hidden', 'true'); main.append(probe);
  const settle = () => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  const results = [];
  try {
    for (const [top, bottom] of [[0, 0], [24, 34]]) {
      properties.forEach((name, index) => root.style.setProperty(name, `${[top, bottom][index]}px`));
      await settle();
      const before = nav.getBoundingClientRect();
      if (before.bottom > innerHeight - bottom + 1) throw new Error('Navigation extends below the safe viewport');
      main.scrollTop = main.scrollHeight;
      await settle();
      if (main.scrollTop <= 0) throw new Error('Page content cannot scroll');
      window.scrollTo(0, 10000);
      await settle();
      const after = nav.getBoundingClientRect();
      if (scrollY !== 0 || document.scrollingElement.scrollHeight > innerHeight + 1)
        throw new Error('Safe-area padding created a scrollable document');
      if (Math.abs(before.top - after.top) > .5 || Math.abs(before.bottom - after.bottom) > .5)
        throw new Error('Navigation moved while page content scrolled');
      results.push(`insets ${top}/${bottom}px: content scrolls; document and navigation stay fixed`);
      main.scrollTop = 0;
    }
    return results;
  } finally {
    probe.remove();
    properties.forEach((name, index) => saved[index][0]
      ? root.style.setProperty(name, ...saved[index]) : root.style.removeProperty(name));
    main.scrollTop = originalScroll;
  }
}
