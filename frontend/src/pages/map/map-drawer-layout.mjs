/** 依据实际遮挡判断，包含拖动和吸附动画；忽略全展开时的亚像素误差。 */
export function isMapAttributionVisible(occlusionHeight, expandedHeight) {
  return Number.isFinite(occlusionHeight) && Number.isFinite(expandedHeight)
    && occlusionHeight >= 0 && expandedHeight - occlusionHeight > 1;
}
