import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { build } from 'esbuild';
import { JSDOM } from 'jsdom';

const compiled = await build({
  entryPoints: [fileURLToPath(new URL('./CodingTrialPanel.jsx', import.meta.url))],
  bundle: true, write: false, platform: 'node', format: 'cjs', jsx: 'automatic', packages: 'external',
  plugins: [{ name: 'local-trial-api', setup(builder) {
    builder.onResolve({ filter: /^\.\/workflowApi$/ }, () => ({ path: 'workflowApi', namespace: 'test' }));
    builder.onLoad({ filter: /.*/, namespace: 'test' }, () => ({ contents: `
      export const ARM_LABELS = { general: '일반', selected: '선택' };
      export const codingWork = (...args) => globalThis.trialTestApi(...args);
      export const downloadText = () => {};
      export const formatSeconds = value => String(value);
      export const observedSeconds = () => 0;
    ` }));
  } }],
});

test('작업 요청 동기화, 직접 편집 보존, 고정 기록과 새 비교 전환', async () => {
  const dom = new JSDOM('<!doctype html><div id="root"></div>', { url: 'https://example.test/' });
  Object.assign(globalThis, { window: dom.window, document: dom.window.document,
    HTMLElement: dom.window.HTMLElement, IS_REACT_ACT_ENVIRONMENT: true });
  Object.defineProperty(globalThis, 'navigator', { configurable: true, value: dom.window.navigator });
  const require = createRequire(import.meta.url);
  const React = require('react');
  const { createRoot } = require('react-dom/client');
  const module = { exports: {} };
  new Function('require', 'module', 'exports', compiled.outputFiles[0].text)(require, module, module.exports);
  const Panel = module.exports.default;
  const root = createRoot(document.getElementById('root'));
  const calls = [];
  let saved;
  globalThis.trialTestApi = async (path, body) => {
    calls.push({ path, body });
    if (path === 'trials' && !body) return { trials: saved ? [structuredClone(saved)] : [] };
    if (path === 'trials' && body) {
      saved = { ...body, id: 'saved', revision: 1, order: ['general', 'selected'], active: null,
        prompts: { general: '고정 일반 지침', selected: '고정 선택 지침' },
        preference: 'unselected', preference_reason: '',
        comparison: { seconds: {}, edit_seconds: {}, both_passed: false },
        arms: Object.fromEntries(['general', 'selected'].map(arm => [arm, {
          outcome: 'unverified', evidence: '', answer: '', timed: {}, seconds: {}, passed_tests: null, total_tests: null,
        }])) };
      return { trial: structuredClone(saved) };
    }
    if (path === 'trials/saved') return { trial: structuredClone(saved) };
    throw new Error(`Unexpected request: ${path}`);
  };
  let task = '첫 작업';
  const render = async next => {
    task = next;
    await React.act(async () => root.render(React.createElement(Panel, {
      source: {}, selected: { snapshot: 'snapshot' }, user: { id: 1 }, task,
    })));
  };
  const field = () => document.querySelector('form textarea');
  const fill = async (input, value) => React.act(async () => {
    Object.getOwnPropertyDescriptor(Object.getPrototypeOf(input), 'value').set.call(input, value);
    input.dispatchEvent(new dom.window.Event('input', { bubbles: true }));
    input.dispatchEvent(new dom.window.Event('change', { bubbles: true }));
  });
  const click = async label => {
    const button = [...document.querySelectorAll('button')].find(node => node.textContent.trim() === label);
    assert.ok(button, label);
    assert.equal(button.disabled, false);
    await React.act(async () => button.click());
  };
  try {
    await render(task);
    assert.equal(field().value, '첫 작업');
    const formFields = [...document.querySelectorAll('form input, form textarea')];
    for (const [index, value] of [[0, '이름'], [1, '도구'], [2, '모델'], [4, '완료 조건']]) {
      await fill(formFields[index], value);
    }
    const initialCalls = calls.length;
    await render('최신 작업');
    assert.equal(field().value, '최신 작업');
    await render('');
    assert.equal(field().value, '');
    assert.deepEqual([...document.querySelectorAll('form input')].map(node => node.value), ['이름', '도구', '모델']);
    assert.equal(document.querySelectorAll('form textarea')[1].value, '완료 조건');
    await render('원문');
    await fill(field(), '수정');
    await fill(field(), '원문');
    await render('부모 변경');
    assert.equal(field().value, '원문');
    await fill(field(), '');
    await render('다음 부모 변경');
    assert.equal(field().value, '');
    assert.equal(calls.length, initialCalls, '동기화와 직접 입력은 API를 호출하지 않는다');
    await fill(field(), '고정 과제');
    await React.act(async () => document.querySelector('form').dispatchEvent(new dom.window.Event('submit', { bubbles: true, cancelable: true })));
    assert.equal(saved.task, '고정 과제');
    await fill(document.querySelector('.coding-work-arm textarea:not([readonly])'), '미저장 검사 근거');
    const fixedCalls = calls.length;
    await render('새 작업 원문');
    assert.match(document.querySelector('pre').textContent, /고정 과제/);
    assert.match(document.querySelector('.coding-work-arm textarea[readonly]').value, /고정 선택 지침|고정 일반 지침/);
    assert.equal(document.querySelector('.coding-work-arm textarea:not([readonly])').value, '미저장 검사 근거');
    window.confirm = () => false;
    await click('새 작업 비교');
    assert.equal(document.querySelector('form'), null);
    assert.equal(document.querySelector('.coding-work-arm textarea:not([readonly])').value, '미저장 검사 근거');
    window.confirm = () => true;
    await click('새 작업 비교');
    assert.equal(field().value, '새 작업 원문');
    await render('새 비교 최신 원문');
    assert.equal(field().value, '새 비교 최신 원문');
    assert.equal(calls.length, fixedCalls);
    await click('열기');
    await render('불러온 뒤 부모 변경');
    assert.match(document.querySelector('pre').textContent, /고정 과제/);
    assert.equal(saved.task, '고정 과제');
    await click('새 작업 비교');
    assert.equal(field().value, '불러온 뒤 부모 변경');
    await render('');
    assert.equal(field().value, '');
    await fill(field(), '새 비교 직접 입력');
    await render('무시할 부모 변경');
    assert.equal(field().value, '새 비교 직접 입력');
  } finally {
    await React.act(async () => root.unmount());
    dom.window.close();
    delete globalThis.trialTestApi;
  }
});
