import test from 'node:test';
import assert from 'node:assert/strict';
import { compareRemixAxes } from './remixComparison.js';

test('순서가 바뀌어도 항목으로 대응하고 방식 변경·출처 변경·같음을 구분한다', () => {
  const before = [
    { axis: 'code', value: 'separated', source: 'team' },
    { axis: 'type', value: 'explicit', source: 'personal' },
    { axis: 'style', value: 'theme', source: 'shared' },
  ];
  const after = [before[2], { ...before[1], source: 'team' }, { ...before[0], value: 'compact', source: 'personal' }];
  assert.deepEqual(compareRemixAxes(before, after).map((r) => [r.axis, r.status]), [
    ['code', 'changed'], ['type', 'source'], ['style', 'same'],
  ]);
  assert.equal(before[0].value, 'separated');
});

test('미정은 빈 값으로 비교하고 없는 기록은 같거나 달랐다고 추측하지 않는다', () => {
  const before = [{ axis: 'a', value: '', source: 'personal' }, { axis: 'b', value: '', source: 'shared' },
    { axis: 'c', value: 'old', source: 'team' }];
  const after = [{ axis: 'a', value: 'new', source: 'team' }, before[1], { axis: 'd', value: 'new', source: 'team' }];
  assert.deepEqual(compareRemixAxes(before, after).map((r) => r.status), ['changed', 'same', 'unknown', 'unknown']);
  assert.equal(compareRemixAxes([before[0]], [{ ...before[0], source: 'unknown' }])[0].status, 'unknown');
  assert.deepEqual(compareRemixAxes([], []), []);
});
