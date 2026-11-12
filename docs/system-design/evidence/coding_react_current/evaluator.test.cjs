'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');
const path = require('node:path');
const { createRequire } = require('node:module');
const { inspectCandidate, typecheckCandidate, loadCandidate, evaluateCandidate } = require('./evaluate.cjs');
const frontendRequire = createRequire(path.resolve(__dirname, '../../frontend/package.json'));

// These fixed development controls are reviewed with the evaluator. They are
// not benchmark candidates and do not measure generated answer quality.
const task = {
  id: 'development_counter',
  contract_types: 'interface ExpectedProps { initial: number; onChange: (value: number) => void; }',
};
const validSource = `import { useState } from 'react';
export type Props = { initial: number; onChange: (value: number) => void };
export function Component({ initial, onChange }: Props) {
  const [count, setCount] = useState(initial);
  return <button onClick={() => { const next = count + 1; setCount(next); onChange(next); }}>{count}</button>;
}`;
const candidate = source => ({ files: { 'Component.tsx': source } });

function developmentRuntime() {
  const { JSDOM } = frontendRequire('jsdom');
  const React = frontendRequire('react');
  const keys = ['window', 'document', 'navigator', 'HTMLElement', 'Event', 'MouseEvent', 'IS_REACT_ACT_ENVIRONMENT'];
  const original = new Map(keys.map(key => [key, Object.getOwnPropertyDescriptor(globalThis, key)]));
  let dom;
  return {
    testNames: () => ['initial_count', 'click_updates_and_emits'],
    installDom() {
      dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost/' });
      for (const key of keys) {
        Object.defineProperty(globalThis, key, { configurable: true, writable: true,
          value: key === 'IS_REACT_ACT_ENVIRONMENT' ? true : dom.window[key] });
      }
    },
    async runTask(id, exports) {
      assert.equal(id, task.id);
      const { createRoot } = frontendRequire('react-dom/client');
      const container = dom.window.document.createElement('div');
      dom.window.document.body.appendChild(container);
      const root = createRoot(container);
      const calls = [];
      const checks = [];
      async function check(name, operation) {
        try { await operation(); checks.push({ name, passed: true }); }
        catch (error) { checks.push({ name, passed: false, error: error.message }); }
      }
      try {
        await check('initial_count', async () => {
          await React.act(async () => root.render(React.createElement(exports.Component, { initial: 2, onChange: value => calls.push(value) })));
          assert.equal(container.querySelector('button')?.textContent, '2');
        });
        await check('click_updates_and_emits', async () => {
          const button = container.querySelector('button');
          assert.ok(button, 'button must be rendered');
          await React.act(async () => button.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })));
          assert.equal(container.querySelector('button')?.textContent, '3');
          assert.deepEqual(calls, [3]);
        });
      } finally {
        await React.act(async () => root.unmount());
        container.remove();
      }
      return checks;
    },
    cleanupDom() {
      dom?.window.close();
      for (const [key, descriptor] of original) {
        if (descriptor) Object.defineProperty(globalThis, key, descriptor);
        else delete globalThis[key];
      }
    },
  };
}

test('development control: typed counter passes real TypeScript and React events', async () => {
  const report = await evaluateCandidate(task, candidate(validSource), { reviewed: true, runtime: developmentRuntime() });
  assert.equal(report.safety.passed, true);
  assert.equal(report.types.passed, true, JSON.stringify(report.types));
  assert.equal(report.runtime.passed, true, JSON.stringify(report.runtime));
  assert.equal(report.runtime.checks.length, 2);
});

test('development control: incorrect callback contract fails types while runtime still works', async () => {
  const source = validSource.replace('onChange: (value: number)', 'onChange: (value: string)')
    .replace('onChange(next)', 'onChange(next as unknown as string)');
  const report = await evaluateCandidate(task, candidate(source), { reviewed: true, runtime: developmentRuntime() });
  assert.equal(report.types.passed, false);
  assert.ok(report.types.diagnostics.some(item => item.file === '__contract_witness__.tsx'));
  assert.equal(report.runtime.passed, true, JSON.stringify(report.runtime));
});

test('development control: well-typed inert button fails the behavioral assertion', async () => {
  const source = validSource.replace('const next = count + 1; setCount(next); onChange(next);', 'void setCount; void onChange;');
  const report = await evaluateCandidate(task, candidate(source), { reviewed: true, runtime: developmentRuntime() });
  assert.equal(report.types.passed, true, JSON.stringify(report.types));
  assert.equal(report.runtime.passed, false);
  assert.deepEqual(report.runtime.checks.map(check => check.passed), [true, false]);
});

test('development control: invalid syntax, paths, imports, and runtime escapes are rejected', async () => {
  const invalidCandidates = [
    candidate('export function Component( {'),
    candidate("import fs from 'node:fs'; export const Component = () => null;"),
    candidate("export const Component = () => import('react');"),
    candidate('export const Component = () => process.cwd();'),
    candidate("export const Component = () => ({}).constructor;"),
    candidate("export const Component = () => ({})['__proto__'];"),
    candidate('export const Component = () => __candidate_require("node:fs");'),
    { files: { 'Component.tsx': validSource, '../escape.ts': 'export {};' } },
    { files: { 'Component.tsx': validSource, 'hidden.d.ts': 'declare const hidden: number;' } },
  ];
  for (const input of invalidCandidates) {
    const report = await evaluateCandidate(task, input, { reviewed: true });
    assert.equal(report.safety.passed, false);
    assert.equal(report.runtime.status, 'skipped');
  }
});

test('runtime authorization is explicit and never inferred from clean static checks', async () => {
  const report = await evaluateCandidate(task, candidate(validSource));
  assert.equal(report.types.passed, true);
  assert.equal(report.runtime.reason, 'explicit_review_required');
  assert.throws(() => loadCandidate(candidate(validSource)), /reviewed=true/);
});

test('all candidate source files are typechecked, including unreferenced helpers', () => {
  const input = { files: { 'Component.tsx': validSource, 'unused.ts': 'export const broken: number = "wrong";' } };
  const report = typecheckCandidate(task, input);
  assert.equal(report.passed, false);
  assert.ok(report.diagnostics.some(item => item.file === 'unused.ts' && item.code === 2322));
});

test('relative modules use the same in-memory module map for typecheck and runtime', async () => {
  const source = validSource.replace("import { useState } from 'react';", "import { useState } from 'react';\nimport { advance } from './logic/_advance.impl';")
    .replace('count + 1', 'advance(count)');
  const input = { files: { 'Component.tsx': source, 'logic/_advance.impl.ts': 'export const advance = (value: number): number => value + 1;' } };
  const report = await evaluateCandidate(task, input, { reviewed: true, runtime: developmentRuntime() });
  assert.equal(report.types.passed, true, JSON.stringify(report.types));
  assert.equal(report.runtime.passed, true, JSON.stringify(report.runtime));
});

test('explicit any is not a clean type pass even without compiler errors', () => {
  const report = typecheckCandidate(task, candidate(`${validSource}\nconst escape: any = 1; void escape;`));
  assert.equal(report.compilerPassed, true);
  assert.equal(report.explicitAny.length, 1);
  assert.equal(report.typeSuppressions.length, 0);
  assert.equal(report.passed, false);
});

test('the public contract requires the named Props type export', () => {
  const report = typecheckCandidate(task, candidate(validSource.replace('export type Props', 'type Props')));
  assert.equal(report.passed, false);
  assert.ok(report.diagnostics.some(item => item.file === '__contract_witness__.tsx' && item.message.includes('Props')));
  const extraRequired = `export type Props = { initial: number; onChange: (value: number) => void; extra: string };
    export function Component({ initial }: { initial: number; onChange: (value: number) => void }) { return <button>{initial}</button>; }`;
  const incompatible = typecheckCandidate(task, candidate(extraRequired));
  assert.equal(incompatible.passed, false);
  assert.ok(incompatible.diagnostics.some(item => item.file === '__contract_witness__.tsx' && item.message.includes('extra')));
});

test('candidate DOM references point to the isolated runtime document', async () => {
  const source = validSource.replace('const next = count + 1;', `
    if (window.document !== document) return;
    document.querySelector('button')?.focus();
    if (!(document.activeElement instanceof HTMLButtonElement)) return;
    if (document.activeElement?.tagName !== 'BUTTON') return;
    const next = count + 1;`);
  const report = await evaluateCandidate(task, candidate(source), { reviewed: true, runtime: developmentRuntime() });
  assert.equal(report.safety.passed, true);
  assert.equal(report.types.passed, true, JSON.stringify(report.types));
  assert.equal(report.runtime.passed, true, JSON.stringify(report.runtime));
});

test('suppressed compiler errors cannot become a clean type pass; any is recorded separately', async () => {
  const source = `// @ts-nocheck\n${validSource}\nconst hidden: number = 'wrong';\nconst escape: any = hidden;\nvoid escape;`;
  const report = await evaluateCandidate(task, candidate(source), { reviewed: true, runtime: developmentRuntime() });
  assert.equal(report.types.compilerPassed, true);
  assert.equal(report.types.passed, false);
  assert.equal(report.types.typeSuppressions[0].directive, '@ts-nocheck');
  assert.equal(report.types.explicitAny.length, 1);
  assert.equal(report.runtime.passed, true);
  const clean = inspectCandidate(candidate(`${validSource}\nconst description = '@ts-ignore'; void description;`));
  assert.equal(clean.typeSuppressions.length, 0);
});

test('empty checks are a harness failure and cleanup always runs', async () => {
  let cleaned = false;
  const runtime = {
    testNames: () => ['required'],
    installDom() {},
    runTask: async () => [],
    cleanupDom() { cleaned = true; },
  };
  const report = await evaluateCandidate(task, candidate(validSource), { reviewed: true, runtime });
  assert.equal(report.runtime.status, 'harness_error');
  assert.equal(report.runtime.passed, false);
  assert.equal(cleaned, true);
});

test('candidate load errors and harness failures remain distinct', async () => {
  let cleaned = 0;
  const runtime = {
    testNames: () => ['required'], installDom() {},
    runTask() { throw new Error('harness failure'); }, cleanupDom() { cleaned += 1; },
  };
  const loadFailure = await evaluateCandidate(task, candidate(`${validSource}\nthrow new Error('candidate failure');`), { reviewed: true, runtime });
  assert.equal(loadFailure.runtime.status, 'candidate_error');
  const harnessFailure = await evaluateCandidate(task, candidate(validSource), { reviewed: true, runtime });
  assert.equal(harnessFailure.runtime.status, 'harness_error');
  assert.equal(cleaned, 2);
});

test('console warnings are diagnostics and do not change functional verdicts', async () => {
  const source = `${validSource}\nconsole.warn('development diagnostic');`;
  const report = await evaluateCandidate(task, candidate(source), { reviewed: true, runtime: developmentRuntime() });
  assert.equal(report.runtime.passed, true);
  assert.ok(report.console.some(item => item.level === 'warn' && item.message === 'development diagnostic'));
});
