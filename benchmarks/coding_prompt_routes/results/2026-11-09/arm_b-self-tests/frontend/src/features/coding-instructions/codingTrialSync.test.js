import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { build } from 'esbuild';
import { JSDOM } from 'jsdom';

const require = createRequire(import.meta.url);
const compiled = await build({
  entryPoints: [fileURLToPath(new URL('./CodingTrialPanel.jsx', import.meta.url))],
  bundle: true, write: false, platform: 'node', format: 'cjs', jsx: 'automatic', packages: 'external',
});

function record(task = '저장된 작업') {
  return {
    id: 'trial-1', revision: 1, title: '기존 비교', task, context: '기존 완료 조건', tool: '도구', model: '모델',
    order: ['general', 'selected'], active: null, server_now: 100,
    preference: 'unselected', preference_reason: '', prompts: { general: '일반 고정', selected: '선택 고정' },
    comparison: { seconds: { general: null, selected: null }, both_passed: false },
    arms: Object.fromEntries(['general', 'selected'].map(arm => [arm, {
      seconds: { setup: 0, edit: 0 }, timed: { setup: false, edit: false }, outcome: 'unverified',
      evidence: '저장된 근거', answer: '', passed_tests: null, total_tests: null,
    }])),
  };
}

async function mount(task = '처음 요청', saved = null) {
  const dom = new JSDOM('<div id="root"></div>', { url: 'https://example.test/' });
  Object.assign(globalThis, { window: dom.window, document: dom.window.document,
    HTMLElement: dom.window.HTMLElement, IS_REACT_ACT_ENVIRONMENT: true });
  Object.defineProperty(globalThis, 'navigator', { configurable: true, value: dom.window.navigator });
  let trial = saved;
  const calls = [];
  globalThis.fetch = async (path, options = {}) => {
    calls.push({ path, options });
    let data;
    if (path === '/api/coding-work/trials' && options.method !== 'POST') data = { trials: trial ? [trial] : [] };
    else if (path === '/api/coding-work/trials') {
      const body = JSON.parse(options.body);
      trial = { ...record(), ...body };
      data = { trial };
    } else if (path === '/api/coding-work/trials/trial-1') data = { trial };
    else throw new Error(`Unexpected request: ${path}`);
    return { ok: true, json: async () => structuredClone(data) };
  };
  const React = require('react');
  const { createRoot } = require('react-dom/client');
  const module = { exports: {} };
  new Function('require', 'module', 'exports', compiled.outputFiles[0].text)(require, module, module.exports);
  const Panel = module.exports.default;
  const root = createRoot(document.getElementById('root'));
  const props = { source: {}, selected: { snapshot: 'snapshot' }, user: { id: 1 }, task };
  const render = async nextTask => {
    props.task = nextTask;
    await React.act(async () => root.render(React.createElement(Panel, props)));
  };
  await render(task);
  const fill = async (element, value) => React.act(async () => {
    Object.getOwnPropertyDescriptor(Object.getPrototypeOf(element), 'value').set.call(element, value);
    element.dispatchEvent(new dom.window.Event('input', { bubbles: true }));
    element.dispatchEvent(new dom.window.Event('change', { bubbles: true }));
  });
  const click = async label => {
    const button = [...document.querySelectorAll('button')].find(node => node.textContent.trim() === label);
    assert.ok(button, label);
    assert.equal(button.disabled, false);
    await React.act(async () => button.click());
  };
  return { render, fill, click, calls,
    taskInput: () => document.querySelector('form textarea'),
    submit: async () => React.act(async () => document.querySelector('form').dispatchEvent(
      new dom.window.Event('submit', { bubbles: true, cancelable: true }))),
    close: async () => { await React.act(async () => root.unmount()); dom.window.close(); },
  };
}

test('미편집 작업은 빈 요청까지 동기화하고 다른 입력과 API 호출 수는 유지한다', async () => {
  const ui = await mount();
  try {
    assert.equal(ui.taskInput().value, '처음 요청');
    const inputs = document.querySelectorAll('form input');
    for (const [index, value] of ['작업 이름', '도구 설정', '모델 설정'].entries()) await ui.fill(inputs[index], value);
    await ui.fill(document.querySelectorAll('form textarea')[1], '완료 조건');
    const callsBefore = ui.calls.length;
    for (const value of ['다음 요청', '', '다시 요청']) {
      await ui.render(value);
      assert.equal(ui.taskInput().value, value);
    }
    assert.deepEqual([...document.querySelectorAll('form input')].map(input => input.value), ['작업 이름', '도구 설정', '모델 설정']);
    assert.equal(document.querySelectorAll('form textarea')[1].value, '완료 조건');
    assert.equal(ui.calls.length, callsBefore);
    await ui.submit();
    assert.equal(JSON.parse(ui.calls.find(call => call.options.method === 'POST').options.body).task, '다시 요청');
  } finally { await ui.close(); }
});

test('직접 비운 작업과 원문으로 되돌린 작업도 편집 상태로 보존한다', async () => {
  for (const value of ['', '처음 요청']) {
    const ui = await mount();
    try {
      await ui.fill(ui.taskInput(), '직접 수정');
      await ui.fill(ui.taskInput(), value);
      await ui.render('부모의 새 요청');
      assert.equal(ui.taskInput().value, value);
    } finally { await ui.close(); }
  }
});

test('시작·불러온 기록은 고정하고 새 비교 확인 후 최신 요청을 다시 따른다', async () => {
  for (const saved of [null, record()]) {
    const ui = await mount('처음 요청', saved);
    try {
      if (saved) await ui.click('열기');
      else { await ui.fill(ui.taskInput(), '직접 입력한 작업'); await ui.submit(); }
      const prompts = [...document.querySelectorAll('textarea[readonly]')].map(input => input.value);
      const evidence = document.querySelector('.coding-work-arm label textarea:not([readonly])');
      await ui.fill(evidence, '아직 저장하지 않은 근거');
      const callsBefore = ui.calls.length;
      await ui.render('최신 부모 요청');
      assert.deepEqual([...document.querySelectorAll('textarea[readonly]')].map(input => input.value), prompts);
      assert.equal(evidence.value, '아직 저장하지 않은 근거');
      window.confirm = () => false;
      await ui.click('새 작업 비교');
      assert.equal(ui.taskInput(), null);
      assert.equal(evidence.value, '아직 저장하지 않은 근거');
      window.confirm = () => true;
      await ui.click('새 작업 비교');
      assert.equal(ui.taskInput().value, '최신 부모 요청');
      await ui.render('새 비교의 다음 요청');
      assert.equal(ui.taskInput().value, '새 비교의 다음 요청');
      await ui.fill(ui.taskInput(), '새 비교에서 직접 편집');
      await ui.render('또 바뀐 부모 요청');
      assert.equal(ui.taskInput().value, '새 비교에서 직접 편집');
      assert.equal(ui.calls.length, callsBefore);
    } finally { await ui.close(); }
  }
});
