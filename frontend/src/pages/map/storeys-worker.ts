import { storeysBuffers, storeysInput, buildStoreysData } from './storeys.mjs';

// One sequential worker per mounted scene, terminated when leaving the page.
export function createStoreysWorker() {
  const worker = new Worker(new URL('./storeys.worker.ts', import.meta.url), { type: 'module' });
  let rejectPending: ((error: Error) => void) | undefined;
  let disposed = false;
  function prepare(input: ReturnType<typeof storeysInput>) {
    if (disposed) return Promise.reject(new Error('地图初始化已取消'));
    if (rejectPending) return Promise.reject(new Error('地图楼层计算仍在进行'));
    return new Promise<ReturnType<typeof buildStoreysData>>((resolve, reject) => {
      rejectPending = reject;
      worker.onmessage = event => {
        rejectPending = undefined;
        if (event.data.error) reject(new Error(event.data.error));
        else resolve(event.data.data);
      };
      worker.onerror = () => { rejectPending = undefined; reject(new Error('地图楼层计算失败')); };
      worker.postMessage(input, storeysBuffers(input) as ArrayBuffer[]);
    });
  }
  function dispose() {
    disposed = true;
    worker.terminate();
    rejectPending?.(new Error('地图初始化已取消'));
    rejectPending = undefined;
  }
  return { prepare, dispose };
}
