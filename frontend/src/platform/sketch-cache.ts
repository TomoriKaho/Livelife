// WebView IndexedDB is private to the app origin and survives process restarts.
// Browser previews use their origin's IndexedDB; unavailable storage is optional.
export type SketchRecord = { key: string; blob: Blob; width: number; height: number; touched: number; identity?: string; namespace?: string; context?: string };
export type SketchStore = {
  get: (key: string) => Promise<SketchRecord | undefined>;
  put: (record: SketchRecord) => Promise<void>;
  remove: (key: string) => Promise<void>;
  touch?: (key: string) => Promise<void>;
  restore?: (namespace: string, context: string) => Promise<SketchRecord[] | undefined>;
  markPrepared?: (namespace: string, context: string, keys: string[]) => Promise<void>;
  close: () => void;
};
export const sketchCacheNamespace = 'pencil-png-v1:rounded-font-v1:default-theme';
export async function sketchCacheKey(source: string, ratio: number, namespace = sketchCacheNamespace) {
  const bytes = new TextEncoder().encode(`${namespace}\n${ratio}\n${source}`);
  const digest = await crypto.subtle.digest('SHA-256', bytes);
  return Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, '0')).join('');
}

export function createSketchStore(name = 'livelife-sketch-cache', maxBytes = 32 * 1024 * 1024): SketchStore {
  let database: IDBDatabase | undefined, opening: Promise<IDBDatabase | undefined> | undefined;
  let disabled = false;
  const timeoutMs = 1000;
  let lastTouch = 0;
  const touched = () => { lastTouch = Math.max(Date.now(), lastTouch + 1); return lastTouch; };
  async function open() {
    if (disabled) return undefined;
    if (database) return database;
    if (!opening) opening = new Promise(resolve => {
      let settled = false;
      const finish = (db?: IDBDatabase) => {
        if (settled) { db?.close(); return; }
        settled = true; clearTimeout(timer);
        if (disabled && db) { db.close(); db = undefined; }
        if (!db) disabled = true;
        else { database = db; db.onversionchange = () => { db.close(); database = undefined; disabled = true; }; }
        resolve(db);
      };
      const timer = setTimeout(() => finish(), timeoutMs);
      try {
        const request = indexedDB.open(name, 2);
        request.onupgradeneeded = () => {
          for (const store of ['images', 'metadata', 'prepared']) {
            if (!request.result.objectStoreNames.contains(store)) request.result.createObjectStore(store, { keyPath: 'key' });
          }
        };
        request.onsuccess = () => finish(request.result);
        request.onerror = () => finish();
        request.onblocked = () => finish();
      } catch { finish(); }
    });
    return opening;
  }
  async function transact<T>(mode: IDBTransactionMode,
    work: (store: IDBObjectStore, set: (result: T) => void, metadata: IDBObjectStore, prepared: IDBObjectStore) => void): Promise<T | undefined> {
    const db = await open();
    if (!db || disabled) return undefined;
    return new Promise(resolve => {
      let tx: IDBTransaction | undefined, value: T | undefined, settled = false;
      const finish = (ok: boolean) => {
        if (settled) return;
        settled = true; clearTimeout(timer); resolve(ok ? value : undefined);
      };
      const timer = setTimeout(() => {
        disabled = true;
        try { tx?.abort(); } catch { /* Already completed. */ }
        finish(false);
      }, timeoutMs);
      try {
        tx = db.transaction(['images', 'metadata', 'prepared'], mode);
        tx.oncomplete = () => finish(true);
        tx.onabort = tx.onerror = () => finish(false);
        work(tx.objectStore('images'), result => { value = result; }, tx.objectStore('metadata'), tx.objectStore('prepared'));
      } catch { finish(false); }
    });
  }
  return {
    async get(key) {
      return transact<SketchRecord>('readwrite', (store, set, metadata) => {
        const request = store.get(key);
        request.onsuccess = () => {
          const record = request.result as SketchRecord | undefined;
          if (record?.blob instanceof Blob && record.blob.type === 'image/png'
            && record.blob.size > 0 && record.blob.size <= maxBytes
            && Number.isInteger(record.width) && record.width > 0
            && Number.isInteger(record.height) && record.height > 0
            && record.width * record.height <= 4 * 1024 * 1024) {
            metadata.put({ key, size: record.blob.size, touched: touched(), identity: record.identity, namespace: record.namespace, context: record.context }); set(record);
          }
        };
      });
    },
    async put(record) {
      if (!record.blob.size || record.blob.size > maxBytes) return;
      await transact('readwrite', (store, _set, metadata) => {
        // One transaction serializes competing writes and atomically evicts + inserts.
        // Read at most 512 small metadata rows, never collect PNG blobs into JS memory.
        const entries: Array<{ key: IDBValidKey; size: number; touched: number }> = [];
        let bytes = record.blob.size;
        const request = metadata.getAll();
        request.onsuccess = () => {
          for (const item of request.result as Array<{ key: string; size: number; touched: number }>) {
            if (item.key === record.key) continue;
            const size = Number(item.size) || 0;
            entries.push({ key: item.key, size, touched: Number(item.touched) || 0 });
            bytes += size;
          }
          entries.sort((a, b) => a.touched - b.touched);
          while (entries.length && (bytes > maxBytes || entries.length >= 512)) {
            const old = entries.shift()!; store.delete(old.key); metadata.delete(old.key); bytes -= old.size;
          }
          store.put(record);
          metadata.put({ key: record.key, size: record.blob.size, touched: touched(), identity: record.identity, namespace: record.namespace, context: record.context });
        };
      });
    },
    async remove(key) { await transact('readwrite', (store, _set, metadata) => { store.delete(key); metadata.delete(key); }); },
    async touch(key) {
      await transact('readwrite', (_images, _set, metadata) => {
        const request = metadata.get(key);
        request.onsuccess = () => { if (request.result) metadata.put({ ...request.result, touched: touched() }); };
      });
    },
    async restore(namespace, context) {
      return transact<SketchRecord[]>('readonly', (images, set, _metadata, prepared) => {
        const marker = prepared.get(`${namespace}:${context}`);
        marker.onsuccess = () => {
          const keys = marker.result?.keys as unknown;
          if (!Array.isArray(keys) || !keys.length || keys.length > 512 || !keys.every(k => typeof k === 'string') || new Set(keys).size !== keys.length) return;
          const records: SketchRecord[] = [];
          for (const key of keys) {
            const request = images.get(key);
            request.onsuccess = () => {
              const r = request.result as SketchRecord | undefined;
              if (r?.identity && r.namespace === namespace && r.context === context
                && r.blob instanceof Blob && r.blob.type === 'image/png' && r.blob.size > 0 && r.blob.size <= maxBytes
                && Number.isInteger(r.width) && r.width > 0 && Number.isInteger(r.height) && r.height > 0
                && r.width * r.height <= 4 * 1024 * 1024) records.push(r);
              if (records.length === keys.length) set(records);
            };
          }
        };
      });
    },
    async markPrepared(namespace, context, keys) {
      if (!keys.length || keys.length > 512) return;
      await transact('readwrite', (_images, _set, _metadata, prepared) => {
        const request = prepared.getAll();
        request.onsuccess = () => {
          const others = request.result.filter(item => item.key !== `${namespace}:${context}`).sort((a, b) => a.touched - b.touched);
          while (others.length >= 8) prepared.delete(others.shift()!.key);
          prepared.put({ key: `${namespace}:${context}`, keys, touched: touched() });
        };
      });
    },
    close() { disabled = true; database?.close(); database = undefined; },
  };
}
