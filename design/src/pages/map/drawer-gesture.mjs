export function drawerHeights(shellHeight, headerHeight, navHeight) {
  const available = Math.max(0, shellHeight - headerHeight - navHeight);
  return {
    collapsed: Math.min(shellHeight * .25, available),
    expanded: Math.min(shellHeight * .75, available),
  };
}

export function draggedHeight(startHeight, deltaY, heights) {
  return Math.max(heights.collapsed, Math.min(heights.expanded, startHeight - deltaY));
}

export function shouldExpand({ wasExpanded, deltaY, deltaX, height, heights }) {
  // 横向浏览活动卡片不改变抽屉；明确的纵向手势优先按方向吸附。
  if (Math.abs(deltaY) <= Math.abs(deltaX) * 1.2) return wasExpanded;
  if (Math.abs(deltaY) >= 32) return deltaY < 0;
  if (Math.abs(deltaY) < 8) return wasExpanded;
  return height > (heights.collapsed + heights.expanded) / 2;
}
