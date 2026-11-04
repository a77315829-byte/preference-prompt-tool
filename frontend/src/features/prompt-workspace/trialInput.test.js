import test from 'node:test';
import assert from 'node:assert/strict';
import { readTrialInput, updateTrialInput } from './trialInput.js';

const variables = [{ name: 'notes', type: 'string' }, { name: 'count', type: 'integer' }, { name: 'approved', type: 'boolean' }];

test('빈 글·숫자 0·아니오도 폼에서 입력한 값으로 유지한다', () => {
  const text = JSON.stringify({ notes: '', count: 0, approved: false });
  assert.deepEqual(readTrialInput(text, variables), { notes: '', count: 0, approved: false });
});

test('복잡한 자료와 잘못된 JSON·타입은 직접 편집할 수 있게 남긴다', () => {
  for (const text of ['{', '[]', 'null', '{"count":"두 개"}']) assert.equal(readTrialInput(text, variables), null);
  assert.equal(readTrialInput('{"items":[]}', [{ name: 'items', type: 'array' }]), null);
});

test('입력칸을 고쳐도 다른 자료를 보존하고, 비운 선택 항목만 제외한다', () => {
  let text = '{"notes":"회의 내용","count":2,"extra":{"keep":true}}';
  text = updateTrialInput(text, 'approved', false);
  text = updateTrialInput(text, 'count', null);
  assert.deepEqual(JSON.parse(text), { notes: '회의 내용', approved: false, extra: { keep: true } });
  assert.deepEqual(readTrialInput(text, variables), JSON.parse(text));
});
