import test from 'node:test';
import assert from 'node:assert/strict';
import { lineageGroups, lineageOf } from './lineageModel.js';

const node = (id, parent = null) => ({ id, title: id, created_at: id, lineage: { kind: parent ? 'remix' : 'task', parent: parent ? { id: parent, title: parent, revision: 1 } : null } });

test('분기한 새 조합과 복원 조합을 부모 아래에 한 번씩 표시한다', () => {
  const items = [node('d', 'b'), node('b', 'a'), node('c', 'a'), node('a'), node('z')];
  assert.deepEqual(lineageGroups(items).map((rows) => rows.map(({ item, depth }) => [item.id, depth])), [
    [['a', 0], ['b', 1], ['d', 2], ['c', 1]], [['z', 0]],
  ]);
  assert.equal(lineageGroups(items, ['d']).length, 1);
  assert.equal(lineageGroups(items, ['d'])[0].length, 4);
});

test('삭제·이전 연결 미기록·순환 참조에서도 항목을 잃거나 이름으로 추측하지 않는다', () => {
  const items = [node('a', 'b'), node('b', 'a'), node('c', 'missing'), node('same')];
  items.push({ id: 'legacy', title: 'legacy', lineage: { kind: 'derived', parent: { title: 'same', revision: 1 } } });
  const rows = lineageGroups(items).flat();
  assert.equal(rows.length, items.length);
  assert.equal(new Set(rows.map((r) => r.item.id)).size, items.length);
  assert.equal(rows.find((r) => r.item.id === 'legacy').depth, 0);
  assert.equal(lineageOf({ provenance: { operation: 'restore', remixed_from: { id: 'parent' } } }).parent.id, 'parent');
});
