import test from 'node:test';
import assert from 'node:assert/strict';
import { mount } from '../../../test-support/appHarness.js';
import { CODING_CHOICES } from './codingOptions.js';
import { comparisonSequence, comparisonSummary } from './repeatedComparison.js';

const pairs = context => Object.entries(CODING_CHOICES).map(([axis, field]) => ({
  id: `${context}:${axis}`, axis, context, label: field.label, question: field.label,
  options: Object.entries(field.options).map(([value, label]) => ({ value, label, code: `${context} ${value}`, explanation: label })),
}));
const examples = { version: 3, language: 'Python', framework: 'FastAPI', notice: '8~10회 비교',
  source: { id: 'test-repeated-v1', kind: 'framework', label: '주문·대여 비교' },
  pairs: [...pairs('order'), ...pairs('rental')], followups: pairs('print') };
const response = data => ({ ok: true, status: 200, json: async () => structuredClone(data) });
const api = async (path, options) => {
  if (path === '/api/auth/me') return response({ user: { id: 1, username: 'alice' } });
  if (path === '/api/preferences') return response({ preferences: [] });
  if (path === '/api/coding-instructions/optimizations') return response({ enabled: false });
  if (path === '/api/coding-instructions/optimizations/recent') return response({ jobs: [] });
  if (path === '/api/coding-instructions/examples') {
    assert.equal(JSON.parse(options.body).protocol, 'repeated-v1');
    return response({ examples });
  }
  if (path === '/api/coding-instructions/preview') return response({ draft: { profile: JSON.parse(options.body).profile, prompt: '반복 비교로 만든 지침' } });
  return null;
};
const press = (ui, selector) => ui.act(async () => document.querySelector(selector).click());
async function enter(ui) { await press(ui, '[aria-label="코딩 도움 선택"]'); await press(ui, '.selection-button'); }

test('unanimous comparisons finish at eight; disagreement stays unresolved with at most two followups', () => {
  const answers = Object.fromEntries(examples.pairs.map(pair => [pair.id, pair.options[0].value]));
  assert.equal(comparisonSequence(examples, answers).length, 8);
  for (const pair of examples.pairs.slice(4)) answers[pair.id] = pair.options[1].value;
  const sequence = comparisonSequence(examples, answers);
  assert.equal(sequence.length, 10);
  for (const pair of sequence.slice(8)) answers[pair.id] = pair.options[0].value;
  const summary = comparisonSummary(sequence, answers);
  assert.ok(Object.values(summary).every(value => value.value === null && value.status === 'mixed'));
});

test('8회 비교 도중 메뉴 이동 복구 → 신호 확인 → 지침·작업 요청 복구', async () => {
  const ui = await mount('https://example.test/', 'coding', api);
  try {
    await enter(ui); await press(ui, '[aria-label="Python 선택"]'); await press(ui, '[aria-label="FastAPI 선택"]');
    await ui.click('코드 예시 비교 시작하기 →');
    for (let index = 0; index < 8; index++) {
      if (index === 3) {
        await ui.click('내 선호 보관함'); await ui.click('시작하기'); await enter(ui);
        assert.match(document.querySelector('.coding-example-comparison').textContent, /4번째 \/ 8회/);
      }
      await press(ui, '.coding-option-select');
      await ui.click(index === 7 ? '4가지 선택 확인하기 →' : '이 선택으로 다음 →');
    }
    assert.match(document.querySelector('[aria-label="반복 비교에서 확인한 신호"]').textContent, /8회 비교/);
    assert.equal(document.querySelectorAll('[aria-label="반복 비교에서 확인한 신호"] li').length, 4);
    await ui.click('내 선택으로 프롬프트 만들기'); await ui.fill('#coding-new-task', '이 작업 요청도 복구');
    await ui.click('내 선호 보관함'); await ui.click('시작하기'); await enter(ui);
    assert.equal(document.querySelector('#coding-instructions-prompt').value, '반복 비교로 만든 지침');
    assert.equal(document.querySelector('#coding-new-task').value, '이 작업 요청도 복구');
  } finally { await ui.close(); }
});

test('10회 뒤에도 미확정 선호를 기본값으로 채우지 않는다', async () => {
  const ui = await mount('https://example.test/', 'coding', api);
  try {
    await enter(ui); await press(ui, '[aria-label="Python 선택"]'); await press(ui, '[aria-label="FastAPI 선택"]');
    await ui.click('코드 예시 비교 시작하기 →');
    for (let index = 0; index < 10; index++) {
      await ui.act(async () => document.querySelectorAll('.coding-option-select')[index >= 4 && index < 8 ? 1 : 0].click());
      await ui.click(index === 9 ? '4가지 선택 확인하기 →' : '이 선택으로 다음 →');
    }
    const generate = [...document.querySelectorAll('button')].find(button => button.textContent === '내 선택으로 프롬프트 만들기');
    assert.equal(generate.disabled, true);
    assert.match(document.querySelector('[aria-label="반복 비교에서 확인한 신호"]').textContent, /미확정/);
  } finally { await ui.close(); }
});
