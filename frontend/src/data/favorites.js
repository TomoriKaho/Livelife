// Demo routes only. Account favorites live in state/favorites.ts.
export const activityMapRoute = item => ({ path: '/map', query: { activity: item.id } });
export const activityDetailRoute = item => ({ path: '/detail', query: { id: item.id } });
