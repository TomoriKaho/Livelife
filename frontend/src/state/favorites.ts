import { onAuthSessionChange, readAuthToken } from '../api/auth';
import { favoriteMembership, favoritePage, isInformationId, setFavorite } from '../api/favorites';
import { createFavorites } from './favorites-core';

export const favorites = createFavorites({ token: readAuthToken, membership: favoriteMembership, page: favoritePage, write: setFavorite });
onAuthSessionChange(() => { favorites.clear(); });
const queued = new Set<string>();
let scheduled = false;
export function checkFavorites(ids: string[]) {
  ids.filter(isInformationId).forEach(id => queued.add(id));
  if (scheduled) return;
  scheduled = true;
  queueMicrotask(() => { scheduled = false; const ids = [...queued]; queued.clear(); void favorites.check(ids); });
}
function refresh() {
  if (!readAuthToken()) return;
  checkFavorites(Object.keys(favorites.state.saved));
  if (favorites.state.loaded || favorites.state.error) void favorites.load();
}
window.addEventListener('focus', refresh);
document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(); });
