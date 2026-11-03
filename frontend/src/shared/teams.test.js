import test from 'node:test';
import assert from 'node:assert/strict';
import { MAX_RECENT, formatUtc, groupByCategory, withRecent } from './teams.js';
import { categoryLabel, flowOfDomain, axisValueLabel } from './domainLabels.js';

test('팀 목록을 카테고리별로 묶고, 최근 카테고리가 위에 온다', () => {
  const groups = groupByCategory([
    { code: 'a', domain_key: 'email' },
    { code: 'b', domain_key: 'coding' },
    { code: 'c', domain_key: 'email' },
  ]);
  assert.deepEqual(groups.map((g) => [g.domainKey, g.items.map((t) => t.code)]), [
    ['email', ['a', 'c']],
    ['coding', ['b']],
  ]);
  assert.deepEqual(groupByCategory([]), []);
});

test('최근 본 팀: 같은 코드는 맨 앞으로 옮기고 개수를 제한한다', () => {
  let list = [];
  for (let i = 0; i < MAX_RECENT + 2; i += 1) list = withRecent(list, { code: `t${i}`, domain_key: 'coding' });
  assert.equal(list.length, MAX_RECENT);
  assert.equal(list[0].code, `t${MAX_RECENT + 1}`);
  list = withRecent(list, { code: 't5', domain_key: 'coding' });
  assert.equal(list[0].code, 't5');
  assert.equal(list.filter((t) => t.code === 't5').length, 1);
});

test('화면 이름: 카테고리, 비교 화면 흐름, 축 값', () => {
  assert.equal(categoryLabel('coding'), '코딩 도움');
  assert.equal(categoryLabel('unknown'), 'unknown');
  assert.equal(flowOfDomain('idle_tracker'), 'idleTracker');
  assert.equal(flowOfDomain('email'), 'email');
  assert.equal(axisValueLabel('code_structure', 'compact'), '간결하게 작성');
  assert.equal(axisValueLabel('code_structure', 'other'), 'other');
});

test('시각은 분까지 UTC 로', () => {
  assert.equal(formatUtc('2026-10-15T09:30:12+00:00'), '2026-10-15 09:30 UTC');
  assert.equal(formatUtc(''), '');
});
