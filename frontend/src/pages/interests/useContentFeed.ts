import { onBeforeUnmount, ref, watch, type Ref } from 'vue';
import { fetchContent, type ContentArticle, type ContentFilters } from '../../api/content';

export function useContentFeed(filters: Ref<ContentFilters>) {
  const items = ref<ContentArticle[]>([]), loading = ref(false), error = ref('');
  const nextOffset = ref<number | null>(null);
  let generation = 0, controller: AbortController | undefined;
  let debounce: ReturnType<typeof setTimeout> | undefined;
  async function load(more = false) {
    clearTimeout(debounce);
    if (more && (loading.value || nextOffset.value === null)) return;
    const offset = more ? nextOffset.value! : 0;
    const current = ++generation;
    controller?.abort();
    const active = new AbortController(); controller = active;
    if (!more) { items.value = []; nextOffset.value = null; }
    loading.value = true; error.value = '';
    const timeout = setTimeout(() => active.abort(), 10_000);
    try {
      const result = await fetchContent({ ...filters.value }, offset, active.signal);
      if (current !== generation) return;
      items.value = [...new Map([...items.value, ...result.items].map(item => [item.id, item])).values()];
      nextOffset.value = result.next_offset;
    } catch (cause) {
      if (current === generation) error.value = active.signal.aborted ? '内容读取超时，请重试。'
        : cause instanceof TypeError ? '网络不可用，请检查连接后重试。'
        : cause instanceof Error ? cause.message : '内容读取失败，请重试。';
    } finally {
      clearTimeout(timeout);
      if (current === generation) loading.value = false;
    }
  }
  watch(filters, () => {
    generation++; controller?.abort(); clearTimeout(debounce);
    items.value = []; nextOffset.value = null; error.value = ''; loading.value = true;
    debounce = setTimeout(() => void load(), 300);
  }, { deep: true, flush: 'sync' });
  void load();
  onBeforeUnmount(() => { generation++; controller?.abort(); clearTimeout(debounce); });
  return { items, loading, error, nextOffset, reload: () => load(), loadMore: () => load(true), retry: () => load(items.value.length > 0) };
}
