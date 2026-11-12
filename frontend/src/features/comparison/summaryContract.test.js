import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { build } from 'esbuild';
import { JSDOM } from 'jsdom';

const compiled = await build({
  entryPoints: [fileURLToPath(new URL('./SummaryContractPanel.jsx', import.meta.url))],
  bundle: true, write: false, platform: 'node', format: 'cjs', jsx: 'automatic',
  packages: 'external', loader: { '.css': 'empty' }, logLevel: 'silent',
});
const require = createRequire(import.meta.url);
const SOURCE = 'The launch is planned. Testing is unfinished. Funding is conditional.';
const SENTENCES = ['The launch is planned.', 'Testing is unfinished.', 'Funding is conditional.'];
const initialProfile = { length: 'short', extractiveness: 'fully', topic: '' };
const response = (body, status = 200) => ({ ok: status === 200, status, json: async () => structuredClone(body) });
const ready = (body) => ({
  status: 'ready', available_sentences: SENTENCES, conflict: null, resolution: body.resolution,
  original_profile: body.profile,
  effective_profile: { ...body.profile, ...(body.resolution === 'expand' ? { length: 'normal' } : {}) },
  notices: ['의미상 압축 가능 여부는 별도로 확인해야 합니다.'],
  prompts: { ko: '확인된 재사용 지침', en: 'Reusable instructions' },
  task_requests: { ko: `확인된 재사용 지침\n${body.requiredSentences.join('\n')}\n${body.sourceText}`, en: `Reusable instructions\n${body.sourceText}` },
});

async function mount(handler = (body) => response(ready(body)), props = {}) {
  const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', { url: 'https://example.test/' });
  Object.assign(globalThis, { window: dom.window, document: dom.window.document,
    HTMLElement: dom.window.HTMLElement, IS_REACT_ACT_ENVIRONMENT: true });
  Object.defineProperty(globalThis, 'navigator', { configurable: true, value: dom.window.navigator });
  const state = { requests: [], copied: [] };
  Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: async (text) => state.copied.push(text) } });
  globalThis.fetch = async (path, options) => {
    assert.equal(path, '/api/summary-contract');
    assert.equal(options.method, 'POST');
    assert.equal(options.headers['Content-Type'], 'application/json');
    const body = JSON.parse(options.body);
    state.requests.push(body);
    return handler(body, options);
  };
  const React = require('react');
  const { createRoot } = require('react-dom/client');
  const module = { exports: {} };
  new Function('require', 'module', 'exports', compiled.outputFiles[0].text)(require, module, module.exports);
  const root = createRoot(document.getElementById('root'));
  await React.act(async () => root.render(React.createElement(module.exports.default,
    { domainKey: 'summarization', initialSource: SOURCE, initialProfile, ...props })));
  const findButton = label => [...document.querySelectorAll('button')].find(button => button.textContent.trim() === label);
  const click = async label => {
    const button = findButton(label);
    assert.ok(button, `Missing button ${label}`); assert.equal(button.disabled, false);
    await React.act(async () => button.click());
  };
  const fill = async (selector, value) => {
    const input = document.querySelector(selector); assert.ok(input, selector);
    await React.act(async () => {
      Object.getOwnPropertyDescriptor(Object.getPrototypeOf(input), 'value').set.call(input, value);
      input.dispatchEvent(new dom.window.Event('input', { bubbles: true }));
      input.dispatchEvent(new dom.window.Event('change', { bubbles: true }));
    });
  };
  return { state, click, fill, findButton, act: React.act, dom, close: async () => {
    await React.act(async () => root.unmount()); dom.window.close();
  } };
}

test('미정 조건을 기본값으로 채우거나 자동 요청하지 않는다', async () => {
  const ui = await mount(undefined, { initialProfile: {} });
  try {
    assert.equal(ui.state.requests.length, 0);
    assert.equal(document.querySelector('[aria-label="요약 분량"]').value, '');
    assert.equal(document.querySelector('[aria-label="원문 표현 방식"]').value, '');
    assert.equal(ui.findButton('조건 확인').disabled, true);
    await ui.fill('[aria-label="요약 분량"]', 'short');
    assert.equal(ui.findButton('조건 확인').disabled, true);
    await ui.fill('[aria-label="원문 표현 방식"]', 'fully');
    await ui.click('조건 확인');
    assert.deepEqual(ui.state.requests[0].profile, initialProfile);
    assert.equal(ui.state.requests[0].resolution, null);
  } finally { await ui.close(); }
});

test('발췌 충돌은 명시적 선택 후에만 해소하고 원문 포함 복사를 구분한다', async () => {
  const ui = await mount(body => body.requiredSentences.length === 3 && !body.resolution
    ? response({ status: 'needs_resolution', available_sentences: SENTENCES,
      conflict: { required_sentences: 3, max_sentences: 2, message: '3문장을 2문장 안에 모두 발췌할 수 없습니다.' },
      original_profile: body.profile, effective_profile: body.profile, notices: [], prompts: {}, task_requests: {} })
    : response(ready(body)));
  try {
    await ui.click('조건 확인');
    await ui.act(async () => document.querySelectorAll('[type="checkbox"]').forEach(input => input.click()));
    assert.equal(document.querySelector('.summary-contract-result'), null);
    await ui.click('조건 확인');
    assert.match(document.querySelector('[role="alert"]').textContent, /3문장을 2문장/);
    assert.equal(ui.findButton('재사용 지침만 복사'), undefined);
    assert.equal(ui.findButton('조건 확인').disabled, true);
    assert.equal(document.querySelector('[type="radio"]:checked'), null);
    await ui.act(async () => document.querySelector('[type="radio"][value="expand"]').click());
    assert.equal(document.querySelector('.summary-contract-result'), null);
    await ui.click('조건 확인');
    assert.equal(ui.state.requests.at(-1).resolution, 'expand');
    assert.equal(ui.state.requests.at(-1).profile.length, 'short');
    assert.deepEqual(ui.state.requests.at(-1).requiredSentences, SENTENCES);
    const values = [...document.querySelectorAll('dd')].map(node => node.textContent);
    assert.match(values[0], /1~2문장/); assert.match(values[1], /3~4문장/);
    await ui.click('재사용 지침만 복사');
    assert.equal(ui.state.copied.at(-1), '확인된 재사용 지침');
    await ui.click('원문·남길 문장과 함께 복사');
    assert.ok(ui.state.copied.at(-1).includes(SOURCE));
    assert.equal(ui.state.requests.length, 3, 'Copy must not request another analysis or model');
  } finally { await ui.close(); }
});

test('프로필·선택 문장·원문 변경이 이전 출력과 선택 처리 방식을 무효화한다', async () => {
  const ui = await mount();
  try {
    await ui.click('조건 확인');
    await ui.act(async () => document.querySelector('[type="checkbox"]').click());
    assert.equal(document.querySelector('.summary-contract-result'), null);
    await ui.click('조건 확인');
    assert.equal(ui.state.requests.at(-1).requiredSentences.length, 1);
    await ui.fill('[aria-label="요약 분량"]', 'long');
    assert.equal(document.querySelector('.summary-contract-result'), null);
    await ui.click('조건 확인');
    assert.equal(ui.state.requests.at(-1).profile.length, 'long');
    await ui.fill('.summary-contract-source', 'A different source.');
    assert.equal(document.querySelector('.summary-contract-result'), null);
    assert.equal(document.querySelectorAll('[type="checkbox"]').length, 0);
    await ui.click('조건 확인');
    assert.deepEqual(ui.state.requests.at(-1).requiredSentences, []);
    assert.equal(ui.state.requests.at(-1).resolution, null);
    assert.equal(ui.state.requests.at(-1).sourceText, 'A different source.');
  } finally { await ui.close(); }
});

test('입력 변경 뒤 늦게 도착한 응답이 오래된 문장·지침을 복구하지 않는다', async () => {
  let finish; let pendingBody; let signal;
  const ui = await mount((body, options) => {
    pendingBody = body; signal = options.signal;
    return new Promise(resolve => { finish = resolve; });
  });
  try {
    await ui.click('조건 확인');
    assert.equal(ui.findButton('조건 확인 중…').disabled, true);
    await ui.fill('.summary-contract-source', 'Updated text.');
    assert.equal(signal.aborted, true);
    await ui.act(async () => finish(response(ready(pendingBody))));
    assert.equal(document.querySelector('.summary-contract-result'), null);
    assert.equal(document.querySelectorAll('[type="checkbox"]').length, 0);
    assert.equal(document.querySelector('.summary-contract-source').value, 'Updated text.');
    assert.equal(ui.findButton('조건 확인').disabled, false);
  } finally { await ui.close(); }
});

test('서버 오류·잘못된 응답에는 복사 가능한 지침을 남기지 않고 재시도할 수 있다', async () => {
  let count = 0;
  const ui = await mount(body => {
    count += 1;
    if (count === 1) return response({ error: '선택 문장이 원문에 없습니다.' }, 400);
    if (count === 2) return response({ status: 'ready' });
    return response(ready(body));
  });
  try {
    await ui.click('조건 확인');
    assert.match(document.querySelector('[role="alert"]').textContent, /원문에 없습니다/);
    assert.equal(ui.findButton('재사용 지침만 복사'), undefined);
    await ui.click('조건 확인');
    assert.match(document.querySelector('[role="alert"]').textContent, /응답을 읽지 못했습니다/);
    await ui.click('조건 확인');
    assert.equal(document.querySelector('[role="alert"]'), null);
    assert.ok(ui.findButton('재사용 지침만 복사'));
  } finally { await ui.close(); }
});

test('문장 선택은 최대 8개이며 이미 고른 문장은 해제할 수 있다', async () => {
  const many = Array.from({ length: 9 }, (_, index) => `Sentence ${index + 1}.`);
  const ui = await mount(body => response({ ...ready(body), available_sentences: many }));
  try {
    await ui.click('조건 확인');
    for (let i = 0; i < 8; i += 1) await ui.act(async () => document.querySelectorAll('[type="checkbox"]')[i].click());
    assert.equal(document.querySelectorAll('[type="checkbox"]:checked').length, 8);
    assert.equal(document.querySelectorAll('[type="checkbox"]')[8].disabled, true);
    assert.equal(document.querySelectorAll('[type="checkbox"]')[0].disabled, false);
    await ui.act(async () => document.querySelectorAll('[type="checkbox"]')[0].click());
    assert.equal(document.querySelectorAll('[type="checkbox"]')[8].disabled, false);
  } finally { await ui.close(); }
});

test('지침 언어를 바꾸면 해당 언어를 복사하며 복사 실패는 안내한다', async () => {
  const ui = await mount();
  try {
    await ui.click('조건 확인');
    await ui.fill('[aria-label="조건 확인 지침 언어"]', 'en');
    await ui.click('재사용 지침만 복사');
    assert.equal(ui.state.copied.at(-1), 'Reusable instructions');
    navigator.clipboard.writeText = async () => { throw new Error('denied'); };
    await ui.click('원문·남길 문장과 함께 복사');
    assert.match(document.querySelector('[role="alert"]').textContent, /직접 선택해 복사/);
    await ui.fill('[aria-label="원문 표현 방식"]', 'normal');
    assert.equal(document.querySelector('[role="alert"]'), null);
    assert.equal(document.querySelector('.summary-contract-result'), null);
  } finally { await ui.close(); }
});

test('긴 원문을 잘라내지 않고 길이 초과를 알리며 요청을 차단한다', async () => {
  const ui = await mount();
  try {
    await ui.click('조건 확인');
    const beforePaste = ui.state.requests.length;
    const overlong = '가'.repeat(12001);
    await ui.fill('.summary-contract-source', overlong);
    const input = document.querySelector('.summary-contract-source');
    assert.equal(input.hasAttribute('maxlength'), false);
    assert.equal(input.value, overlong, 'The entire pasted source must remain editable');
    assert.equal(input.getAttribute('aria-invalid'), 'true');
    assert.match(document.querySelector('[role="alert"]').textContent, /12,001 \/ 12,000자/);
    assert.match(document.querySelector('[role="alert"]').textContent, /내용은 그대로 유지/);
    assert.equal(ui.findButton('조건 확인').disabled, true);
    assert.equal(document.querySelector('.summary-contract-result'), null);
    await ui.act(async () => document.querySelector('.summary-contract form')
      .dispatchEvent(new ui.dom.window.Event('submit', { bubbles: true, cancelable: true })));
    assert.equal(ui.state.requests.length, beforePaste, 'Even form submission cannot send an oversized source');
    // The Python server counts Unicode code points, so a surrogate pair is one character.
    const withinLimit = '🙂'.repeat(12000);
    await ui.fill('.summary-contract-source', withinLimit);
    assert.equal(input.value, withinLimit);
    assert.equal(input.getAttribute('aria-invalid'), 'false');
    assert.equal(ui.findButton('조건 확인').disabled, false);
    assert.equal(document.querySelector('[role="alert"]'), null);
    await ui.click('조건 확인');
    assert.equal(ui.state.requests.at(-1).sourceText, withinLimit);
  } finally { await ui.close(); }
});
