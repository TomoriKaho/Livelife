const colors = new Set(['yellow', 'blue', 'mint', 'pink', 'lavender']);

export function decorationState(element: Pick<HTMLElement, 'dataset' | 'classList'>) {
  const color = colors.has(element.dataset.pencil || '') ? element.dataset.pencil! : '';
  const requestedCast = element.dataset.cast || color;
  const cast = element.classList.contains('nav-item') ? 'yellow' : element.classList.contains('sketch-cast')
    ? (colors.has(requestedCast) ? requestedCast : 'blue')
    : element.classList.contains('art-paper') ? 'blue' : '';
  return { color, cast, white: !color && element.classList.contains('sketch-white'),
    fillOnly: element.classList.contains('sketch-fill-only'), faint: element.classList.contains('page-outlet') };
}

// CSS handles size changes. No measurements, ResizeObserver, image encoding or
// per-control jobs are needed for the static decorations.
export function createStaticSketchRenderer() {
  const layers = new WeakMap<HTMLElement, HTMLSpanElement>();
  function release(element: HTMLElement) {
    layers.get(element)?.remove(); layers.delete(element);
    element.classList.remove('has-sketch', 'static-sketch');
  }
  function update(element: HTMLElement) {
    if (element.matches('.nav-item') && element.getAttribute('aria-current') !== 'page') {
      release(element); return;
    }
    if (!element.matches('.sketch, .nav-item, .bottom-nav, .page-outlet, .icon-button:not(.notification-button)')) {
      release(element); return;
    }
    let layer = layers.get(element);
    if (!layer) {
      layer = document.createElement('span'); layer.className = 'sketch-decoration';
      layer.setAttribute('aria-hidden', 'true'); layers.set(element, layer);
    }
    const state = decorationState(element);
    layer.dataset.color = state.color; layer.dataset.cast = state.cast;
    layer.classList.toggle('fill-only', state.fillOnly);
    layer.classList.toggle('faint', state.faint);
    layer.style.setProperty('--sketch-paper', element.matches('.nav-item')
      ? 'var(--sketch-surface)' : state.white ? '#fff' : 'transparent');
    element.classList.add('has-sketch', 'static-sketch');
    if (layer.parentNode !== element) element.prepend(layer);
  }
  return { update, release };
}
