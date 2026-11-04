import test from 'node:test';
import assert from 'node:assert/strict';
import { promptChanges, selectionMatches } from './comparisonText.js';

test('다른 문장만 표시하고 매우 긴 줄 목록도 LCS 표 없이 처리한다', () => {
  assert.deepEqual(promptChanges('공통\n짧게', '공통\n자세히'), [
    { type: 'removed', text: '짧게' }, { type: 'added', text: '자세히' },
  ]);
  assert.deepEqual(promptChanges('공통\r\n', '공통'), []);
  const long = Array(10000).fill('한 줄').join('\n');
  assert.equal(promptChanges(long, '다른 문장').length, 2);
});

test('개인·팀 선택이나 팀 스냅샷이 달라지면 이전 실행 결과로 구분한다', () => {
  const output = { task: '작업', revision: 2, basis: 'team', team_snapshot: 'first' };
  const item = { revision: 2 };
  assert.equal(selectionMatches(output, '작업', item, 'team', { team_snapshot: 'first' }), true);
  assert.equal(selectionMatches(output, '작업', item, 'personal', null), false);
  assert.equal(selectionMatches(output, '작업', item, 'team', { team_snapshot: 'next' }), false);
});

test('작업용 선택 조합이나 팀 기준이 달라지면 이전 결과로 구분한다', () => {
  const output = { task: '작업', revision: 1, basis: 'custom', team_snapshot: 't1', task_snapshot: 'mixed1' };
  assert.equal(selectionMatches(output, '작업', { revision: 1 }, 'custom', { team_snapshot: 't1' }, { snapshot: 'mixed1' }), true);
  assert.equal(selectionMatches(output, '작업', { revision: 1 }, 'custom', { team_snapshot: 't1' }, { snapshot: 'mixed2' }), false);
  assert.equal(selectionMatches(output, '작업', { revision: 1 }, 'custom', { team_snapshot: 't2' }, { snapshot: 'mixed1' }), false);
  assert.equal(selectionMatches(output, '작업', { revision: 1 }, 'custom', { team_snapshot: 't1' }, null), false);
});
