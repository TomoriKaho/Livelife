import test from 'node:test';
import assert from 'node:assert/strict';
import { defaultCurrentLocationOptions, getCurrentLocation, watchCurrentLocation } from '../src/platform/location.ts';

const granted = { location: 'granted', coarseLocation: 'granted' };
const prompt = { location: 'prompt', coarseLocation: 'prompt' };
const denied = { location: 'denied', coarseLocation: 'denied' };
const position = { coords: { latitude: 39.991, longitude: 116.304, accuracy: 12.5 }, timestamp: 1_700_000_000_000 };

function provider({ check = granted, request = granted, result = position, error } = {}) {
  const calls = [];
  return {
    calls,
    async checkPermissions() { calls.push('check'); return check; },
    async requestPermissions() { calls.push('request'); return request; },
    async getCurrentPosition(options) {
      calls.push(options);
      if (error) throw error;
      return result;
    },
  };
}

test('reports unsupported before calling the default plugin outside a location-capable platform', async () => {
  assert.deepEqual(await getCurrentLocation(), { status: 'error', error: 'unsupported' });
});

test('uses the browser geolocation API to prompt for and obtain a web position', async () => {
  const originalNavigator = Object.getOwnPropertyDescriptor(globalThis, 'navigator');
  const calls = [];
  Object.defineProperty(globalThis, 'navigator', {
    configurable: true,
    value: { geolocation: { getCurrentPosition(resolve, reject, options) { calls.push(options); resolve(position); } } },
  });
  try {
    assert.deepEqual(await getCurrentLocation(), { status: 'success', location: { latitude: 39.991, longitude: 116.304, accuracy: 12.5, timestamp: 1_700_000_000_000 } });
    assert.deepEqual(calls, [defaultCurrentLocationOptions]);
  } finally {
    if (originalNavigator) Object.defineProperty(globalThis, 'navigator', originalNavigator);
    else delete globalThis.navigator;
  }
});

test('requests permission once and returns a minimal current location', async () => {
  const api = provider({ check: prompt });
  const result = await getCurrentLocation({}, api);
  assert.deepEqual(result, { status: 'success', location: { latitude: 39.991, longitude: 116.304, accuracy: 12.5, timestamp: 1_700_000_000_000 } });
  assert.deepEqual(api.calls, ['check', 'request', defaultCurrentLocationOptions]);
});

test('uses an already granted approximate permission and caller options', async () => {
  const api = provider({ check: { location: 'denied', coarseLocation: 'granted' } });
  const result = await getCurrentLocation({ enableHighAccuracy: true, timeout: 5_000 }, api);
  assert.equal(result.status, 'success');
  assert.deepEqual(api.calls, ['check', { enableHighAccuracy: true, timeout: 5_000, maximumAge: 0 }]);
});

test('does not request a position after a denied permission', async () => {
  const api = provider({ check: denied, request: denied });
  assert.deepEqual(await getCurrentLocation({}, api), { status: 'error', error: 'permission-denied' });
  assert.deepEqual(api.calls, ['check', 'request']);
});

test('normalizes native and web errors without exposing their messages', async () => {
  for (const [error, expected] of [
    [{ code: 'OS-PLUG-GLOC-0010', message: 'Could not obtain location in time.' }, 'timeout'],
    [{ code: 1, message: 'ignored' }, 'permission-denied'],
    [{ code: 2, message: 'Position unavailable' }, 'unavailable'],
    [{ message: 'Not implemented on this platform' }, 'unsupported'],
  ]) {
    const api = provider({ error });
    assert.deepEqual(await getCurrentLocation({}, api), { status: 'error', error: expected });
  }
});

test('rejects malformed plugin coordinates as unavailable', async () => {
  const api = provider({ result: { coords: { latitude: Number.NaN, longitude: 116.304, accuracy: 1 }, timestamp: 1 } });
  assert.deepEqual(await getCurrentLocation({}, api), { status: 'error', error: 'unavailable' });
});

test('normalizes a supplied compass heading without requiring one', async () => {
  const api = provider({ result: { ...position, coords: { ...position.coords, heading: 450 } } });
  assert.deepEqual(await getCurrentLocation({}, api), { status: 'success', location: { latitude: 39.991, longitude: 116.304, accuracy: 12.5, timestamp: 1_700_000_000_000, heading: 90 } });
});

test('uses the browser watcher for ongoing web positions and clears it on stop', async () => {
  const originalNavigator = Object.getOwnPropertyDescriptor(globalThis, 'navigator');
  const calls = [], updates = [];
  let success, failure;
  Object.defineProperty(globalThis, 'navigator', {
    configurable: true,
    value: { geolocation: {
      watchPosition(resolve, reject, options) { success = resolve; failure = reject; calls.push(['watch', options]); return 42; },
      clearWatch(id) { calls.push(['clear', id]); },
    } },
  });
  try {
    const stop = await watchCurrentLocation(result => updates.push(result));
    success(position);
    failure({ code: 3 });
    await stop();
    assert.deepEqual(calls, [['watch', defaultCurrentLocationOptions], ['clear', 42]]);
    assert.deepEqual(updates, [
      { status: 'success', location: { latitude: 39.991, longitude: 116.304, accuracy: 12.5, timestamp: 1_700_000_000_000 } },
      { status: 'error', error: 'timeout' },
    ]);
  } finally {
    if (originalNavigator) Object.defineProperty(globalThis, 'navigator', originalNavigator);
    else delete globalThis.navigator;
  }
});

test('requests native permission once, relays watcher updates, and clears the native watch', async () => {
  const updates = [], calls = [];
  let callback;
  const api = {
    ...provider({ check: prompt }),
    async watchPosition(options, listener) { calls.push(['watch', options]); callback = listener; return 'watch-1'; },
    async clearWatch({ id }) { calls.push(['clear', id]); },
  };
  const stop = await watchCurrentLocation(result => updates.push(result), { timeout: 5_000 }, api);
  callback({ ...position, coords: { ...position.coords, heading: 450 } });
  callback(null, { code: 2 });
  await stop();
  assert.deepEqual(api.calls, ['check', 'request']);
  assert.deepEqual(calls, [
    ['watch', { enableHighAccuracy: false, timeout: 5_000, maximumAge: 0 }],
    ['clear', 'watch-1'],
  ]);
  assert.deepEqual(updates, [
    { status: 'success', location: { latitude: 39.991, longitude: 116.304, accuracy: 12.5, timestamp: 1_700_000_000_000, heading: 90 } },
    { status: 'error', error: 'unavailable' },
  ]);
});

test('does not create a watcher after native location permission is denied', async () => {
  const api = {
    ...provider({ check: denied, request: denied }),
    async watchPosition() { throw new Error('must not watch'); },
    async clearWatch() {},
  };
  const updates = [];
  await watchCurrentLocation(result => updates.push(result), {}, api);
  assert.deepEqual(api.calls, ['check', 'request']);
  assert.deepEqual(updates, [{ status: 'error', error: 'permission-denied' }]);
});
