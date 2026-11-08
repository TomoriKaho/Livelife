/** 抽屉档位与地图页浮层（署名、提示）的布局策略；新增档位时在此扩展，避免 MapPage 硬编码。 */

export function drawerOcclusionHeight(state, heights, { dragging = false, dragHeight = 0 } = {}) {
  if (dragging && Number.isFinite(dragHeight)) return dragHeight;
  const value = heights?.[state];
  return Number.isFinite(value) ? value : heights?.middle ?? 0;
}

/** 地图区域仍可见时展示 OSM 署名；全展开遮盖地图时不重复展示。 */
export function isMapAttributionVisible(drawerState) {
  return drawerState !== 'expanded';
}
