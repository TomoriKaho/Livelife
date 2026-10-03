export const drawerStates = ['hidden', 'middle', 'expanded'];

export function drawerHeights(shellHeight, headerHeight, navHeight) {
  const available = Math.max(0, shellHeight - headerHeight - navHeight);
  return {
    hidden: Math.min(38, available),
    middle: Math.max(Math.min(38, available), Math.min(shellHeight * .25, available)),
    expanded: available,
  };
}

export function draggedHeight(startHeight, deltaY, heights) {
  return Math.max(heights.hidden, Math.min(heights.expanded, startHeight - deltaY));
}

export function nextDrawerState(state, direction) {
  return drawerStates[Math.max(0, Math.min(drawerStates.length - 1, drawerStates.indexOf(state) + direction))];
}

export function snapDrawerState({ fromState, deltaY, deltaX, height, heights }) {
  // 横向浏览卡片不换档；短滑动换一档，长距离拖动可跨过中间档。
  if (Math.abs(deltaY) <= Math.abs(deltaX) * 1.2 || Math.abs(deltaY) < 8) return fromState;
  let index = drawerStates.reduce((best, state, i) =>
    Math.abs(height - heights[state]) < Math.abs(height - heights[drawerStates[best]]) ? i : best, 0);
  if (Math.abs(deltaY) >= 32) {
    const step = drawerStates.indexOf(nextDrawerState(fromState, deltaY < 0 ? 1 : -1));
    index = deltaY < 0 ? Math.max(index, step) : Math.min(index, step);
  }
  return drawerStates[index];
}
