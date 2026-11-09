import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { build } from 'esbuild';
import { JSDOM } from 'jsdom';

const require = createRequire(import.meta.url);
const makeTrial = (id, task) => ({
  id, task, title: 'Saved comparison', context: 'Fixed context', tool: 'Tool', model: 'Model',
  revision: 1, order: ['general', 'selected'], active: null, preference: 'unselected', preference_reason: '',
  prompts: { general: 'Fixed general', selected: 'Fixed selected' },
  comparison: { seconds: { general: null, selected: null }, both_checked: false, both_passed: false },
  arms: Object.fromEntries(['general', 'selected'].map(arm => [arm, {
    outcome: 'unverified', evidence: '', answer: '', passed_tests: null, total_tests: null,
    seconds: { setup: 0, edit: 0 }, timed: { setup: false, edit: false },
  }])),
});

test('task follows props until edited; started and loaded records stay fixed until a confirmed new comparison', async () => {
  const compiled = await build({
    entryPoints: [fileURLToPath(new URL('./CodingTrialPanel.jsx', import.meta.url))],
    bundle: true, write: false, platform: 'node', format: 'cjs', jsx: 'automatic', packages: 'external',
    plugins: [{ name: 'local-workflow-stub', setup(builder) {
      builder.onResolve({ filter: /^\.\/workflowApi$/ }, () => ({ path: 'workflow', namespace: 'test' }));
      builder.onLoad({ filter: /.*/, namespace: 'test' }, () => ({ contents: `
        export const ARM_LABELS = {general: 'General', selected: 'Selected'};
        export const codingWork = (...args) => globalThis.trialTaskApi(...args);
        export const downloadText = () => {};
        export const formatSeconds = () => 'Unmeasured';
        export const observedSeconds = () => 0;
      ` }));
    } }],
  });
  const dom = new JSDOM('<div id="root"></div>', { url: 'https://example.test/' });
  Object.assign(globalThis, { window: dom.window, document: dom.window.document,
    HTMLElement: dom.window.HTMLElement, IS_REACT_ACT_ENVIRONMENT: true });
  Object.defineProperty(globalThis, 'navigator', { configurable: true, value: dom.window.navigator });
  const calls = [];
  const loaded = makeTrial('loaded', 'Loaded task');
  globalThis.trialTaskApi = async (path, body) => {
    calls.push({ path, body });
    if (path === 'trials' && !body) return { trials: [loaded] };
    if (path === 'trials') return { trial: { ...makeTrial('created', body.task), ...body } };
    if (path === 'trials/loaded') return { trial: loaded };
    throw new Error(`Unexpected API operation: ${path}`);
  };
  const React = require('react');
  const { createRoot } = require('react-dom/client');
  const module = { exports: {} };
  new Function('require', 'module', 'exports', compiled.outputFiles[0].text)(require, module, module.exports);
  const root = createRoot(document.getElementById('root'));
  const render = task => React.act(async () => root.render(React.createElement(module.exports.default, {
    task, user: { id: 1 }, source: {}, selected: { snapshot: 'snapshot' },
  })));
  const taskInput = () => document.querySelector('form textarea');
  const fill = (element, value) => React.act(async () => {
    Object.getOwnPropertyDescriptor(Object.getPrototypeOf(element), 'value').set.call(element, value);
    element.dispatchEvent(new dom.window.Event('input', { bubbles: true }));
    element.dispatchEvent(new dom.window.Event('change', { bubbles: true }));
  });
  const click = text => React.act(async () => {
    const button = [...document.querySelectorAll('button')].find(node => node.textContent.trim() === text);
    assert.ok(button); assert.equal(button.disabled, false); button.click();
  });
  try {
    await render('Original');
    assert.equal(taskInput().value, 'Original');
    for (const [index, field] of [...document.querySelectorAll('form input')].entries()) await fill(field, `Value ${index}`);
    await fill(document.querySelectorAll('form textarea')[1], 'Completion criteria');
    const initialCalls = calls.length;
    await render('Updated'); assert.equal(taskInput().value, 'Updated');
    await render(''); assert.equal(taskInput().value, '');
    await render('Original');
    assert.deepEqual([...document.querySelectorAll('form input')].map(node => node.value), ['Value 0', 'Value 1', 'Value 2']);
    assert.equal(document.querySelectorAll('form textarea')[1].value, 'Completion criteria');
    await fill(taskInput(), 'Manual');
    await fill(taskInput(), 'Original');
    await render('Parent changed'); assert.equal(taskInput().value, 'Original');
    await fill(taskInput(), '');
    await render('Parent changed again'); assert.equal(taskInput().value, '');
    assert.equal(calls.length, initialCalls, 'synchronization must not call the API');
    await fill(taskInput(), 'Frozen manual task');
    await React.act(async () => document.querySelector('form').dispatchEvent(new dom.window.Event('submit', { bubbles: true, cancelable: true })));
    assert.equal(calls.find(call => call.body).body.task, 'Frozen manual task');
    await fill(document.querySelector('.coding-work-arm textarea:not([readonly])'), 'Unsaved evidence');
    const recordBefore = document.querySelector('.coding-work-columns').textContent;
    const recordCalls = calls.length;
    await render('Latest parent');
    assert.match(document.querySelector('pre').textContent, /Frozen manual task/);
    assert.equal(document.querySelector('.coding-work-columns').textContent, recordBefore);
    assert.equal(document.querySelector('.coding-work-arm textarea:not([readonly])').value, 'Unsaved evidence');
    window.confirm = () => false;
    await click('새 작업 비교');
    assert.match(document.querySelector('pre').textContent, /Frozen manual task/);
    assert.equal(document.querySelector('.coding-work-arm textarea:not([readonly])').value, 'Unsaved evidence');
    window.confirm = () => true;
    await click('새 작업 비교'); assert.equal(taskInput().value, 'Latest parent');
    await render(''); assert.equal(taskInput().value, '');
    await render('Next request'); assert.equal(taskInput().value, 'Next request');
    assert.equal(calls.length, recordCalls);
    await click('열기');
    await render('After loading');
    assert.match(document.querySelector('pre').textContent, /Loaded task/);
    assert.match(document.querySelector('.coding-work-arm textarea').value, /Fixed general/);
    window.confirm = () => false;
    await click('새 작업 비교'); assert.match(document.querySelector('pre').textContent, /Loaded task/);
    window.confirm = () => true;
    await click('새 작업 비교'); assert.equal(taskInput().value, 'After loading');
    await render('Latest submit');
    await React.act(async () => document.querySelector('form').dispatchEvent(new dom.window.Event('submit', { bubbles: true, cancelable: true })));
    assert.equal(calls.filter(call => call.body).at(-1).body.task, 'Latest submit');
  } finally {
    await React.act(async () => root.unmount());
    dom.window.close(); delete globalThis.trialTaskApi;
  }
});
