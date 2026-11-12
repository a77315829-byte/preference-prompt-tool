// Locked before either candidate was generated. Only HTTP is mocked; render real React.
import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const frontend = path.resolve(process.env.PPT_REACT_BENCH_TARGET || path.join(repo, 'frontend'));
const require = createRequire(path.join(repo, 'frontend/package.json'));
const { build } = require('esbuild');
const { JSDOM } = require('jsdom');
const React = require('react');
const compiled = await build({ entryPoints: [path.join(frontend, 'src/features/coding-instructions/CodingTrialPanel.jsx')],
  bundle: true, write: false, platform: 'node', format: 'cjs', jsx: 'automatic', packages: 'external',
  loader: { '.css': 'empty' }, logLevel: 'silent' });
const module = { exports: {} };
new Function('require', 'module', 'exports', compiled.outputFiles[0].text)(require, module, module.exports);
const Panel = module.exports.default;

function frozenTrial(task = '과거 기록의 작업') {
  return { id: 'saved-1', title: '고정 기록', task, context: '고정된 커밋과 검사', tool: '도구', model: '동일 모델',
    revision: 1, server_now: 100, active: null, order: ['general', 'selected'], preference: 'unselected', preference_reason: '',
    prompts: { general: '일반 고정 지침', selected: '선택 고정 지침' },
    comparison: { seconds: { general: null, selected: null }, edit_seconds: { general: null, selected: null },
      timing_complete: false, both_passed: false, both_checked: false, accuracy_basis: '사용자 기록' },
    arms: Object.fromEntries(['general', 'selected'].map(a => [a, { seconds: { setup: 0, edit: 0 }, timed: { setup: false, edit: false },
      outcome: 'unverified', evidence: '', answer: '', passed_tests: null, total_tests: null }])) };
}

async function mount(t, initialTask = '', saved = false) {
  const dom = new JSDOM('<!doctype html><div id="root"></div>', { url: 'https://benchmark.invalid/' });
  Object.assign(globalThis, { window: dom.window, document: dom.window.document, HTMLElement: dom.window.HTMLElement,
    IS_REACT_ACT_ENVIRONMENT: true });
  Object.defineProperty(globalThis, 'navigator', { configurable: true, value: dom.window.navigator });
  let task = initialTask;
  let record = saved ? frozenTrial() : null;
  const writes = [];
  globalThis.fetch = async (url, options = {}) => {
    const body = options.body ? JSON.parse(options.body) : null;
    let data;
    if (body) {
      writes.push({ url, body });
      assert.equal(url, '/api/coding-work/trials', 'Input sync must not create background writes');
      record = { ...frozenTrial(body.task), title: body.title, context: body.context, tool: body.tool, model: body.model };
      data = { trial: record };
    } else if (url === '/api/coding-work/trials') data = { trials: record ? [record] : [] };
    else if (url === '/api/coding-work/trials/saved-1') data = { trial: record };
    else throw new Error('Unexpected request: ' + url);
    return { ok: true, json: async () => structuredClone(data) };
  };
  window.confirm = () => true;
  const { createRoot } = require('react-dom/client');
  const root = createRoot(document.getElementById('root'));
  const render = async next => {
    task = next;
    await React.act(async () => root.render(React.createElement(Panel, { user: { id: 1 }, task,
      source: { profile: { language: 'JavaScript', framework: 'React', preferences: {} } },
      selected: { snapshot: 'frozen-source', prompt: '고정 지침' } })));
  };
  const field = label => {
    const node = [...document.querySelectorAll('label')].find(n => n.textContent.startsWith(label));
    assert.ok(node, `Missing input label: ${label}`);
    return node.querySelector('input, textarea, select');
  };
  const fill = async (label, value) => {
    const input = field(label);
    await React.act(async () => {
      Object.getOwnPropertyDescriptor(Object.getPrototypeOf(input), 'value').set.call(input, value);
      input.dispatchEvent(new dom.window.Event('input', { bubbles: true }));
      input.dispatchEvent(new dom.window.Event('change', { bubbles: true }));
    });
  };
  const click = async text => {
    const button = [...document.querySelectorAll('button')].find(n => n.textContent.trim() === text);
    assert.ok(button, 'Missing button: ' + text); assert.equal(button.disabled, false);
    await React.act(async () => button.click());
  };
  const create = async () => {
    for (const [label, value] of [['작업 이름', '실제 버그'], ['사용할 도구', '같은 도구'], ['모델·추론 설정', '동일 모델'], ['저장소·기준 커밋·완료 조건', 'commit abc; 회귀 검사']]) await fill(label, value);
    await React.act(async () => document.querySelector('form').dispatchEvent(new dom.window.Event('submit', { bubbles: true, cancelable: true })));
  };
  t.after(async () => { await React.act(async () => root.unmount()); dom.window.close(); });
  await render(task);
  return { render, field, fill, click, create, writes };
}

const TASK = '두 조건에 사용할 실제 작업';
test('R1 initial parent task is visible', async t => {
  const ui = await mount(t, '최초 작업'); assert.equal(ui.field(TASK).value, '최초 작업');
});
test('R2 late parent task fills untouched empty draft', async t => {
  const ui = await mount(t); await ui.render('검색 초기화 오류 수정'); assert.equal(ui.field(TASK).value, '검색 초기화 오류 수정');
});
test('R3 untouched draft tracks parent replacement and clearing without writes', async t => {
  const ui = await mount(t, 'A'); await ui.render('B'); assert.equal(ui.field(TASK).value, 'B');
  await ui.render(''); assert.equal(ui.field(TASK).value, ''); assert.equal(ui.writes.length, 0);
});
test('R4 direct edit survives parent changes', async t => {
  const ui = await mount(t, 'A'); await ui.fill(TASK, '내가 직접 수정'); await ui.render('B'); assert.equal(ui.field(TASK).value, '내가 직접 수정');
});
test('R5 deliberately cleared text stays empty', async t => {
  const ui = await mount(t, 'A'); await ui.fill(TASK, ''); await ui.render('B'); assert.equal(ui.field(TASK).value, '');
});
test('R6 editing back to original still counts as manual edit', async t => {
  const ui = await mount(t, 'A'); await ui.fill(TASK, '직접 수정'); await ui.fill(TASK, 'A'); await ui.render('B'); assert.equal(ui.field(TASK).value, 'A');
});
test('R7 parent updates preserve all other draft fields', async t => {
  const ui = await mount(t, 'A');
  for (const label of ['작업 이름', '사용할 도구', '모델·추론 설정', '저장소·기준 커밋·완료 조건']) await ui.fill(label, label + ' 보존');
  await ui.render('B');
  for (const label of ['작업 이름', '사용할 도구', '모델·추론 설정', '저장소·기준 커밋·완료 조건']) assert.equal(ui.field(label).value, label + ' 보존');
  assert.equal(ui.writes.length, 0);
});
test('R8 submitted record remains frozen; new comparison uses latest task and resets edit ownership', async t => {
  const ui = await mount(t, 'A'); await ui.fill(TASK, '직접 제출한 작업'); await ui.create();
  assert.equal(ui.writes[0].body.task, '직접 제출한 작업');
  await ui.render('최신 부모 작업');
  const fixed = [...document.querySelectorAll('textarea[readonly]')].map(n => n.value).join('\n');
  assert.match(fixed, /직접 제출한 작업/); assert.doesNotMatch(fixed, /최신 부모 작업/);
  await ui.click('새 작업 비교'); assert.equal(ui.field(TASK).value, '최신 부모 작업');
  await ui.render('다음 최신 작업'); assert.equal(ui.field(TASK).value, '다음 최신 작업');
  assert.equal(ui.writes.length, 1);
});
test('R9 opening saved record preserves it; cancel keeps it, confirmed new comparison uses current parent', async t => {
  const ui = await mount(t, 'A', true); await ui.click('열기'); await ui.render('B');
  window.confirm = () => false; await ui.click('새 작업 비교');
  assert.match(document.body.textContent, /고정 기록/); assert.equal(document.querySelector('form'), null);
  window.confirm = () => true; await ui.click('새 작업 비교'); assert.equal(ui.field(TASK).value, 'B');
  assert.equal(ui.writes.length, 0);
});
