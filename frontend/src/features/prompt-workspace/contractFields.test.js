import test from 'node:test';
import assert from 'node:assert/strict';
import {
  OBJECT_ITEMS,
  blankInputText,
  contractProblems,
  contractShapeError,
  fieldSummary,
  itemKindOf,
  newField,
  nextFieldName,
  typeLabel,
  withBound,
  withItemKind,
  withType,
} from './contractFields.js';

// 샘플 프로젝트(prompt_workspace/examples/synthetic_cost.py)의 출력 계약과 같은 모양.
const SAMPLE = [
  { name: 'currency', type: 'string', required: true, description: '입력의 통화 그대로' },
  { name: 'summary', type: 'string', required: true, description: '한두 문장 요약' },
  {
    name: 'items', type: 'array', required: true, min_items: 0, description: '서비스별 금액',
    item_fields: [
      { name: 'service', type: 'string', required: true, description: '' },
      { name: 'amount', type: 'string', required: true, description: '' },
    ],
  },
  { name: 'limitations', type: 'array', item_type: 'string', required: false, description: '' },
];

test('타입은 한국어 뒤에 원래 이름을 붙여 보여 준다', () => {
  assert.equal(typeLabel('string'), '글자 (string)');
  assert.equal(typeLabel('array'), '목록 (array)');
  assert.equal(typeLabel('boolean'), '예/아니오 (boolean)');
  assert.equal(typeLabel('mystery'), 'mystery');
});

test('샘플 출력 계약에는 고칠 곳이 없다', () => {
  assert.deepEqual(contractProblems(SAMPLE), []);
});

test('새 항목 이름은 겹치지 않는다', () => {
  assert.equal(nextFieldName([]), 'field_1');
  assert.equal(nextFieldName([{ name: 'field_2' }]), 'field_3');
  assert.equal(nextFieldName([{ name: 'a' }, { name: 'field_3' }]), 'field_4');
  const added = newField(SAMPLE);
  assert.deepEqual(added, { name: 'field_5', type: 'string', required: true, description: '' });
  assert.deepEqual(contractProblems([...SAMPLE, added]), []);
});

test('목록으로 바꾸면 글자 목록이 되고, 다시 바꾸면 목록 칸이 지워진다', () => {
  const list = withType({ name: 'tags', type: 'string', required: true, description: '' }, 'array');
  assert.equal(list.item_type, 'string');
  assert.deepEqual(contractProblems([list]), []);
  const back = withType({ ...list, min_items: 1, max_items: 3 }, 'number');
  assert.deepEqual(back, { name: 'tags', type: 'number', required: true, description: '' });
});

test('목록 안 항목을 묶음과 단일 타입 사이에서 바꾼다', () => {
  const list = { name: 'rows', type: 'array', required: true, description: '', item_type: 'number' };
  assert.equal(itemKindOf(list), 'number');
  const grouped = withItemKind(list, OBJECT_ITEMS);
  assert.equal(itemKindOf(grouped), OBJECT_ITEMS);
  assert.equal('item_type' in grouped, false);
  assert.equal(grouped.item_fields.length, 1);
  assert.deepEqual(contractProblems([grouped]), []);
  const flat = withItemKind(grouped, 'integer');
  assert.equal('item_fields' in flat, false);
  assert.equal(flat.item_type, 'integer');
});

test('개수 칸: 비우면 제한 없음, 숫자면 그 값', () => {
  const list = SAMPLE[3];
  assert.equal(withBound(list, 'max_items', '5').max_items, 5);
  assert.equal('max_items' in withBound({ ...list, max_items: 5 }, 'max_items', ''), false);
  assert.equal('min_items' in withBound(list, 'min_items', 'abc'), false);
});

test('서버가 거부할 내용을 미리 알려 준다', () => {
  const problems = contractProblems([
    { name: 'Summary', type: 'string', required: true, description: '' },
    { name: 'total', type: 'string', required: true, description: '' },
    { name: 'total', type: 'string', required: true, description: '' },
    { name: 'rows', type: 'array', required: true, description: '', item_type: 'string', min_items: 3, max_items: 1 },
    { name: 'bad', type: 'array', required: true, description: '', item_type: 'string', min_items: -1 },
    {
      name: 'nested', type: 'array', required: true, description: '',
      item_fields: [{ name: 'inner', type: 'array', required: true, description: '' }],
    },
  ]);
  assert.equal(problems.length, 5);
  assert.match(problems[0], /^1번째 항목: 이름은/);
  assert.match(problems[1], /^'total': 같은 이름/);
  assert.match(problems[2], /^'rows': 최소 개수가 최대 개수보다/);
  assert.match(problems[3], /^'bad': 최소 개수는 0 이상의 정수/);
  assert.match(problems[4], /^'nested' 안의 'inner': 타입은 글자·숫자·정수·예\/아니오 중 하나/);
});

test('읽기 쉬운 한 줄 설명', () => {
  assert.equal(fieldSummary(SAMPLE[1]), '글자');
  assert.equal(fieldSummary(SAMPLE[2]), '목록 - 한 줄에 service·amount');
  assert.equal(fieldSummary(SAMPLE[3]), '글자 목록');
  assert.equal(fieldSummary({ type: 'object' }), '묶음');
});

test('표로 그릴 수 없는 JSON 은 내용 검사 전에 걸러 낸다', () => {
  assert.equal(contractShapeError(SAMPLE), '');
  assert.equal(contractShapeError({}), '항목 목록([ ... ])이어야 합니다.');
  assert.equal(contractShapeError([null]), '1번째 항목이 { ... } 객체가 아닙니다.');
  assert.equal(
    contractShapeError([{ name: 'rows', type: 'array', item_fields: 'x' }]),
    '1번째 항목의 item_fields: 항목 목록([ ... ])이어야 합니다.',
  );
  assert.deepEqual(contractProblems([{ name: 'ok', type: 'string', required: true }, 'oops']),
    ['2번째 항목이 { ... } 객체가 아닙니다.']);
});

test('필수 여부가 없으면 알려 준다 (JSON 으로 붙여 넣을 때)', () => {
  assert.deepEqual(contractProblems([{ name: 'note', type: 'string' }]),
    ["'note': 필수 여부(required)를 true 나 false 로 정해 주세요."]);
});

test('시험 입력 빈 틀은 변수 이름과 타입별 빈 값이다', () => {
  const text = blankInputText([
    { name: 'customer_message', type: 'string' },
    { name: 'total', type: 'number' },
    { name: 'urgent', type: 'boolean' },
    { name: 'items', type: 'array' },
  ]);
  assert.deepEqual(JSON.parse(text), { customer_message: '', total: 0, urgent: false, items: [] });
  assert.equal(blankInputText([]), '{}');
});
