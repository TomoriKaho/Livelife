import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { buildingDistance, matchActivities, matchBuildingId, nearestNamedBuildings } from '../src/pages/map/nearby.mjs';

const campus = JSON.parse(readFileSync(new URL('../src/assets/maps/campus.json', import.meta.url), 'utf8'));

test('nearest named buildings use the footprint edge and keep empty venues', () => {
  const buildings = [
    { id: 'a', name: '甲楼', points: [[0, 0], [20, 0], [20, 20], [0, 20]], holes: [] },
    { id: 'b', name: '乙楼', points: [[30, 0], [40, 0], [40, 20], [30, 20]], holes: [] },
    { id: 'c', name: '', points: [[21, 0], [22, 0], [22, 20], [21, 20]], holes: [] },
  ];
  assert.equal(buildingDistance([19, 10], buildings[0]), 0);
  assert.equal(buildingDistance([19, 10], buildings[1]), 11);
  assert.deepEqual(nearestNamedBuildings(buildings, [19, 10], 2).map(item => item.id), ['a', 'b']);
});

test('location text matches only one complete campus building name', () => {
  assert.equal(matchBuildingId('理科教学楼 101', campus.buildings), '444991872');
  assert.equal(matchBuildingId('第二教学楼 203', campus.buildings), '240825557');
  assert.equal(matchBuildingId('121楼', campus.buildings), null);
  assert.equal(matchBuildingId('李兆基人文学苑报告厅', campus.buildings), null);
  assert.equal(matchBuildingId('五四体育馆', campus.buildings), null);
  assert.deepEqual(matchActivities([
    { id: '1', location: '理科教学楼 101', start_at: '2026-11-11T12:00:00Z' },
    { id: '2', location: '未知活动地点', start_at: '2026-11-11T10:00:00Z' },
  ], campus.buildings).map(item => item.id), ['1']);
});
