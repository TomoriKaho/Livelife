import { reactive } from 'vue';
import type { FavoritePage, FavoriteStatus } from '../api/favorites';

interface Dependencies {
  token: () => string | null;
  membership: (ids: string[]) => Promise<string[]>;
  page: (status: FavoriteStatus, offset?: number, asOf?: string) => Promise<FavoritePage>;
  write: (id: string, saved: boolean) => Promise<void>;
}
export function createFavorites(deps: Dependencies) {
  const state = reactive({
    saved: {} as Record<string, boolean | undefined>, pending: {} as Record<string, boolean>,
    checking: {} as Record<string, boolean>, errors: {} as Record<string, string>,
    items: [] as FavoritePage['items'], counts: { upcoming: 0, ongoing: 0, ended: 0, unknown: 0 },
    total: 0, category: 'upcoming' as FavoriteStatus, next: null as number | null, asOf: '',
    loading: false, loaded: false, error: '',
  });
  let epoch = 0, listGeneration = 0, listRequested = false;
  const versions = new Map<string, number>();
  const message = (e: unknown) => e instanceof Error ? e.message : '收藏操作失败，请重试。';
  function clear() {
    epoch++; listGeneration++; versions.clear(); listRequested = false;
    state.saved = {}; state.pending = {}; state.checking = {}; state.errors = {};
    state.items = []; state.total = 0; state.counts = { upcoming: 0, ongoing: 0, ended: 0, unknown: 0 };
    state.next = null; state.asOf = ''; state.loading = false; state.loaded = false; state.error = '';
  }
  async function check(ids: string[]) {
    const token = deps.token(), generation = epoch;
    if (!token) return;
    const unique = [...new Set(ids)];
    for (let offset = 0; offset < unique.length; offset += 100) {
      if (epoch !== generation || deps.token() !== token) return;
      const batch = unique.slice(offset, offset + 100), stamps = batch.map(id => versions.get(id) || 0);
      batch.forEach(id => { state.checking[id] = true; });
      try {
        const result = new Set(await deps.membership(batch));
        if (epoch !== generation || deps.token() !== token) return;
        batch.forEach((id, i) => {
          if (!state.pending[id] && stamps[i] === (versions.get(id) || 0)) { state.saved[id] = result.has(id); state.errors[id] = ''; }
        });
      } catch (e) {
        if (epoch === generation && deps.token() === token) batch.forEach((id, i) => {
          if (!state.pending[id] && stamps[i] === (versions.get(id) || 0)) state.errors[id] = message(e);
        });
      } finally { if (epoch === generation) batch.forEach(id => { state.checking[id] = false; }); }
    }
  }
  async function load(more = false) {
    if (!deps.token()) return;
    listRequested = true;
    if (more && (state.loading || state.next === null)) return;
    const generation = ++listGeneration, current = epoch, token = deps.token();
    const offset = more ? state.next! : 0;
    if (!more) { state.items = []; state.next = null; state.loaded = false; }
    state.loading = true; state.error = '';
    try {
      const result = await deps.page(state.category, offset, more ? state.asOf : undefined);
      if (epoch !== current || listGeneration !== generation || deps.token() !== token) return;
      state.items = [...new Map([...state.items, ...result.items].map(item => [item.id, item])).values()];
      state.counts = result.counts; state.total = result.total; state.next = result.next_offset; state.asOf = result.as_of; state.loaded = true;
      result.items.forEach(item => { if (!state.pending[item.id]) state.saved[item.id] = true; });
    } catch (e) { if (epoch === current && listGeneration === generation && deps.token() === token) state.error = message(e); }
    finally { if (epoch === current && listGeneration === generation) state.loading = false; }
  }
  async function set(id: string, saved: boolean) {
    if (state.pending[id]) return false;
    if (!deps.token()) { state.errors[id] = '请先登录后使用收藏。'; return false; }
    const generation = epoch, token = deps.token();
    state.pending[id] = true; state.errors[id] = '';
    versions.set(id, (versions.get(id) || 0) + 1);
    // Invalidate list reads started before this operation, including failed writes.
    listGeneration++; state.loading = false;
    try {
      await deps.write(id, saved);
      if (epoch !== generation || deps.token() !== token) return false;
      state.saved[id] = saved;
      if (!saved) state.items = state.items.filter(item => item.id !== id);
      return true;
    } catch (e) {
      if (epoch === generation && deps.token() === token) state.errors[id] = message(e);
      return false;
    } finally { if (epoch === generation && deps.token() === token) {
      state.pending[id] = false; versions.set(id, (versions.get(id) || 0) + 1);
      listGeneration++; state.loading = false;
      if (listRequested) void load();
    } }
  }
  return { state, clear, check, load, set };
}
