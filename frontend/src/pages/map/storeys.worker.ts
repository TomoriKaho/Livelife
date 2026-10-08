import { buildStoreysData, storeysBuffers, storeysInput } from './storeys.mjs';

self.onmessage = (event: MessageEvent<ReturnType<typeof storeysInput>>) => {
  try {
    const data = buildStoreysData(event.data);
    self.postMessage({ data }, { transfer: storeysBuffers(data) as ArrayBuffer[] });
  } catch (error) {
    self.postMessage({ error: error instanceof Error ? error.message : String(error) });
  }
};
