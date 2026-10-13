// Offline syntax and deterministic interaction checks, using installed esbuild.
// This small hook harness is not a browser, a TS type checker, or a user study.
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import vm from 'node:vm';
import { createRequire } from 'node:module';
import { resolve } from 'node:path';

// Optional tooling directory lets a local checkout reuse installed dependencies.
const require = createRequire(process.argv[2]
  ? resolve(process.argv[2], 'package.json')
  : new URL('./package.json', import.meta.url));
const { build } = require('esbuild');
const jsxRuntime = require('react/jsx-runtime');

const dataset = JSON.parse(await readFile(new URL('./v1.json', import.meta.url), 'utf8'));
const baselines = new Map();
let steps = 0;

function nodes(element) {
  if (Array.isArray(element)) return element.flatMap(nodes);
  if (!element || typeof element !== 'object') return [];
  return [element, ...nodes(element.props.children)];
}

function texts(element) {
  if (Array.isArray(element)) return element.flatMap(texts);
  if (typeof element === 'string' || typeof element === 'number') return [String(element)];
  if (!element || typeof element !== 'object') return [];
  return texts(element.props.children);
}

function snapshot(element) {
  if (Array.isArray(element)) return element.map(snapshot);
  if (!element || typeof element !== 'object') return element;
  return { type: element.type, props: Object.fromEntries(Object.entries(element.props)
    .filter(([, value]) => typeof value !== 'function')
    .map(([key, value]) => [key, key === 'children' ? snapshot(value) : value])) };
}

for (const variant of dataset.variants) {
  const task = dataset.tasks.find((entry) => entry.id === variant.task_id);
  const result = await build({
    entryPoints: [`${task.component}.tsx`], bundle: true, write: false,
    format: 'cjs', platform: 'node', jsx: 'automatic', external: ['react', 'react/jsx-runtime'],
    plugins: [{ name: 'dataset-files', setup(builder) {
      builder.onResolve({ filter: /./ }, (args) => {
        if (args.path.startsWith('react')) return { path: args.path, external: true };
        const path = args.path.replace(/^\.\//, '');
        return { path: variant.files[path] ? path : `${path}.ts`, namespace: 'dataset' };
      });
      builder.onLoad({ filter: /./, namespace: 'dataset' }, (args) => ({
        contents: variant.files[args.path], loader: args.path.endsWith('.tsx') ? 'tsx' : 'ts',
      }));
    } }],
  });
  const state = [];
  let cursor = 0;
  const react = { useState(initial) {
    const slot = cursor++;
    if (!(slot in state)) state[slot] = initial;
    return [state[slot], (next) => { state[slot] = typeof next === 'function' ? next(state[slot]) : next; }];
  } };
  const module = { exports: {} };
  vm.runInNewContext(result.outputFiles[0].text, {
    exports: module.exports, module, require: (name) => {
      if (name === 'react') return react;
      if (name === 'react/jsx-runtime') return jsxRuntime;
      throw new Error(`Unexpected import: ${name}`);
    },
  });
  function render() { cursor = 0; return module.exports[task.component](); }
  let tree = render();
  // Values created inside vm have different Array prototypes, so compare data.
  assert.equal(JSON.stringify(texts(tree)), JSON.stringify(task.expected_initial), `${variant.id}: initial UI`);
  assert.equal(tree.props.style.backgroundColor, '#eef2ff');
  assert.equal(tree.props.style.color, '#172554');
  assert.equal(tree.props.style.padding, 16);
  const history = [snapshot(tree)];
  for (const [action, expected, args = []] of task.trace) {
    const control = nodes(tree).find((node) => node.props.onClick?.name === action);
    if (control) control.props.onClick(...args);
    else if (action === 'update') {
      const input = nodes(tree).find((node) => node.type === 'input');
      assert.ok(input, `${variant.id}: input exists`);
      input.props.onChange({ currentTarget: { value: args[0] } });
    } else assert.fail(`${variant.id}: action ${action} is not connected to a control`);
    tree = render();
    assert.equal(JSON.stringify(state[0]), JSON.stringify(expected), `${variant.id}: ${action}`);
    history.push(snapshot(tree));
    steps += 1;
  }
  // All eight combinations must produce exactly the same UI and state trace.
  const serialized = JSON.stringify(history);
  if (baselines.has(task.id)) assert.equal(serialized, baselines.get(task.id), variant.id);
  else baselines.set(task.id, serialized);
}
console.log(`PASS: ${dataset.variants.length} TS/TSX variants parsed; ${steps} interaction steps; all 8 styles per task have identical rendered traces.`);
