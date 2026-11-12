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
    assert.equal(JSON.parse(options.body).protocol, 'adaptive-v1');
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

const adaptiveExamples = { ...examples, version: 4, max_rounds: 8, followups: [], notice: '최대 8회 · 원하는 시점에 마침' };
function adaptiveApi(captured = []) {
  return async (path, options) => {
    if (path === '/api/coding-instructions/examples') return response({ examples: adaptiveExamples });
    if (path === '/api/coding-instructions/preview') captured.push(JSON.parse(options.body).profile);
    return api(path, options);
  };
}
async function enterAdaptive(ui) {
  await enter(ui); await press(ui, '[aria-label="Python 선택"]'); await press(ui, '[aria-label="FastAPI 선택"]');
  assert.match(document.querySelector('.coding-environment-screen .coding-primary-button')?.textContent || document.querySelector('.coding-next-bar .coding-primary-button').textContent, /직접 고를게요/);
  await ui.click('코드 예시 비교 시작하기 →');
}

test('1회만 비교하고 마쳐도 선택을 보존하고 미비교 항목만 직접 고른다', async () => {
  const captured = [];
  const ui = await mount('https://example.test/', 'coding', adaptiveApi(captured));
  try {
    await enterAdaptive(ui);
    const finish = () => [...document.querySelectorAll('button')].find(button => button.textContent === '여기까지 비교하고 선택 확인하기');
    assert.equal(finish().disabled, true);
    await press(ui, '.coding-option-select');
    await ui.click('여기까지 비교하고 선택 확인하기');
    const signal = document.querySelector('[aria-label="반복 비교에서 확인한 신호"]').textContent;
    assert.match(signal, /1회 선택 · 반복 확인 전/);
    assert.doesNotMatch(signal, /2회 같은 선택/);
    assert.equal(document.querySelectorAll('.coding-preference-buttons [aria-pressed="true"]').length, 1);
    const generate = () => [...document.querySelectorAll('button')].find(button => button.textContent === '내 선택으로 프롬프트 만들기');
    assert.equal(generate().disabled, true);
    for (const axis of ['comments', 'structure', 'output']) {
      const field = CODING_CHOICES[axis];
      await press(ui, `[aria-label="${field.label}: ${Object.values(field.options)[0]}"]`);
    }
    await ui.click('내 선택으로 프롬프트 만들기');
    assert.equal(captured[0].comparison.version, 4);
    assert.deepEqual(captured[0].comparison.rounds, [{ id: 'order:explanation', value: 'brief' }]);
    assert.equal(captured[0].comparison.choices.comments, null);
  } finally { await ui.close(); }
});

test('4회 선택을 복구하고 8회를 채우지 않은 채 지침을 만든다', async () => {
  const captured = [];
  const ui = await mount('https://example.test/', 'coding', adaptiveApi(captured));
  try {
    await enterAdaptive(ui);
    for (let index = 0; index < 4; index++) {
      await press(ui, '.coding-option-select');
      await ui.click('이 선택으로 다음 →');
    }
    await ui.click('내 선호 보관함'); await ui.click('시작하기'); await enter(ui);
    assert.match(document.querySelector('.coding-example-comparison').textContent, /5번째 비교 · 최대 8회/);
    await ui.click('여기까지 비교하고 선택 확인하기');
    assert.equal(document.querySelectorAll('.coding-preference-buttons [aria-pressed="true"]').length, 4);
    await ui.click('내 선택으로 프롬프트 만들기');
    assert.equal(captured[0].comparison.rounds.length, 4);
    assert.ok(Object.values(captured[0].comparison.summary).every(value => value.status === 'single' && !value.consistent));
  } finally { await ui.close(); }
});

test('새 비교는 엇갈려도 8회에서 마치며 9번째 질문을 강제하지 않는다', async () => {
  const ui = await mount('https://example.test/', 'coding', adaptiveApi());
  try {
    await enterAdaptive(ui);
    for (let index = 0; index < 8; index++) {
      await ui.act(async () => document.querySelectorAll('.coding-option-select')[index < 4 ? 0 : 1].click());
      await ui.click(index === 7 ? '4가지 선택 확인하기 →' : '이 선택으로 다음 →');
    }
    assert.equal(document.querySelector('.coding-example-comparison'), null);
    assert.match(document.querySelector('[aria-label="반복 비교에서 확인한 신호"]').textContent, /선택이 엇갈림 · 미확정/);
    assert.equal(document.querySelectorAll('.coding-preference-buttons [aria-pressed="true"]').length, 0);
  } finally { await ui.close(); }
});

test('앞선 선택을 바꾸면 이후 비교 기록을 다시 확인하고 취소는 기존 선택을 보존한다', async () => {
  const ui = await mount('https://example.test/', 'coding', adaptiveApi());
  try {
    await enterAdaptive(ui);
    for (let index = 0; index < 4; index++) { await press(ui, '.coding-option-select'); await ui.click('이 선택으로 다음 →'); }
    await press(ui, '.coding-axis-progress button');
    await press(ui, '.coding-option-select');
    assert.equal([...document.querySelectorAll('.coding-axis-progress button span')].filter(item => item.textContent === '✓').length, 4);
    await ui.act(async () => document.querySelectorAll('.coding-option-select')[1].click());
    await ui.click('여기까지 비교하고 선택 확인하기');
    assert.match(document.querySelector('[aria-label="반복 비교에서 확인한 신호"]').textContent, /1회 비교/);
    assert.equal(document.querySelectorAll('.coding-preference-buttons [aria-pressed="true"]').length, 1);
    await ui.click('코드 예시를 보며 다시 고르기');
    await press(ui, '.coding-option-select');
    await ui.click('비교 취소');
    assert.equal(document.querySelector('[aria-label="설명 방식: 과정과 이유를 단계별로"]').getAttribute('aria-pressed'), 'true');
  } finally { await ui.close(); }
});
