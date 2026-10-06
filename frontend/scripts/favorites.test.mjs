import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { activities } from '../src/data/activities.js';
import { activityStatus, saved, savedActivities, toggleSave, removeSaved, activityMapRoute, activityDetailRoute } from '../src/data/favorites.js';

test('活动开始时进入进行中，结束时进入已结束，使用北京时间', () => {
  const item = activities.find(item => item.id === 'ai');
  assert.equal(activityStatus(item, '2026-10-03T13:59:59+08:00'), 'upcoming');
  assert.equal(activityStatus(item, '2026-10-03T14:00:00+08:00'), 'ongoing');
  assert.equal(activityStatus(item, '2026-10-03T15:29:59+08:00'), 'ongoing');
  assert.equal(activityStatus(item, '2026-10-03T15:30:00+08:00'), 'ended');
  assert.equal(activityStatus(item, '2026-10-02T23:00:00+08:00'), 'upcoming');
});
test('共享收藏添加、重复切换和移除同步更新列表，未知 ID 不进入列表', () => {
  const initial = new Set(saved.value);
  try {
    removeSaved('oct05-innovate');
    toggleSave('oct05-innovate');
    assert.ok(savedActivities.value.some(item => item.id === 'oct05-innovate'));
    toggleSave('oct05-innovate');
    assert.ok(!savedActivities.value.some(item => item.id === 'oct05-innovate'));
    toggleSave('film'); toggleSave('film');
    assert.equal(saved.value.has('film'), initial.has('film'));
    removeSaved('ai'); removeSaved('ai');
    assert.ok(!savedActivities.value.some(item => item.id === 'ai'));
    toggleSave('unknown'); assert.ok(!saved.value.has('unknown'));
  } finally { saved.value = initial; }
});
test('演示收藏覆盖三个状态；每条活动可路由到自身详情和有效地图目标', () => {
  const campus = JSON.parse(readFileSync(new URL('../src/assets/maps/campus.json', import.meta.url), 'utf8'));
  const ids = new Set(campus.buildings.map(item => item.id));
  assert.equal(new Set(savedActivities.value.map(item => activityStatus(item))).size, 3);
  for (const item of activities) {
    assert.deepEqual(activityDetailRoute(item), { path: '/detail', query: { id: item.id } });
    assert.deepEqual(activityMapRoute(item), { path: '/map', query: { activity: item.id } });
    assert.ok(ids.has(item.building) || (item.mapPosition?.length === 2 && item.mapPosition.every(Number.isFinite)), item.title);
  }
});
