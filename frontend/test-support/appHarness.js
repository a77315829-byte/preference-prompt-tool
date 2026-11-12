import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { build } from 'esbuild';
import { JSDOM } from 'jsdom';

// 실제 화면과 상태 전환을 검사한다. 애니메이션과 HTTP만 대체한다.
const source = await build({
  entryPoints: [fileURLToPath(new URL('../src/app/App.jsx', import.meta.url))],
  bundle: true, write: false, platform: 'node', format: 'cjs', jsx: 'automatic',
  packages: 'external', external: ['react', 'react/*', 'react-dom', 'react-dom/*'], loader: { '.css': 'empty' }, logLevel: 'silent',
  plugins: [{ name: 'static-motion', setup(builder) {
    builder.onResolve({ filter: /^motion\/react$/ }, () => ({ path: 'motion', namespace: 'test' }));
    builder.onLoad({ filter: /.*/, namespace: 'test' }, () => ({ contents: `
      import React from 'react';
      const cache = {};
      export const motion = new Proxy({}, { get(_, tag) {
        return cache[tag] ||= React.forwardRef(({ children, initial, animate, exit, transition, whileHover, whileTap, layout, ...props }, ref) => React.createElement(tag, { ...props, ref }, children));
      }});
      export const AnimatePresence = ({children}) => children;
      export const useReducedMotion = () => true;
    `, loader: 'js' }));
  } }],
});
const require = createRequire(import.meta.url);

export async function mount(url, invitedDomain = 'coding', overrideFetch = null) {
  const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', { url });
  Object.assign(globalThis, { window: dom.window, document: dom.window.document, HTMLElement: dom.window.HTMLElement,
    IS_REACT_ACT_ENVIRONMENT: true });
  Object.defineProperty(globalThis, 'navigator', { configurable: true, value: dom.window.navigator });
  dom.window.HTMLElement.prototype.scrollIntoView = () => {};
  const state = { team: { code: 'team-invited', name: '함께 개발팀', domain_key: invitedDomain, members: [], agreements: [], prompts: {}, exports: [] },
    creates: 0, sessions: 0, merges: 0, copied: '' };
  Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: async (text) => { state.copied = text; } } });
  const session = { session_id: 's1', total_rounds: 1, answered: 0, done: false, demo_mode: true, demo_reason: 'live_disabled',
    axes: [], source_text: '팀의 작업 예시', pair: { pair_id: 'p1', a: { text: 'A', combo: { code_structure: 'compact' } },
      b: { text: 'B', combo: { code_structure: 'separated' } } } };
  globalThis.fetch = async (path, options = {}) => {
    if (overrideFetch) {
      const response = await overrideFetch(path, options, state);
      if (response) return response;
    }
    const body = options.body ? JSON.parse(options.body) : {};
    let data;
    if (path === '/api/auth/me') data = { user: null, signupOpen: true };
    else if (path === '/api/health') data = { live: false, liveConfigured: false };
    else if (path === '/api/teams' && options.method === 'POST') {
      state.creates += 1;
      state.team = { ...state.team, name: body.name, domain_key: body.domainKey };
      data = { team: state.team };
    } else if (path === `/api/teams/${state.team.code}`) data = { team: state.team };
    else if (path === '/api/sessions') {
      state.sessions += 1;
      assert.equal(body.domainKey, state.team.domain_key);
      data = { session };
    } else if (path === '/api/sessions/s1/choices') {
      data = { session: { ...session, answered: 1, done: true, pair: null, prompt: '개인 지침', prompts: { ko: '개인 지침' }, prompt_language: 'ko', exports: [] } };
    } else if (path === `/api/teams/${state.team.code}/members`) {
      assert.equal(body.requireExisting, true);
      assert.equal(body.sessionId, 's1');
      state.merges += 1;
      state.team = { ...state.team, members: [body.name], prompt: '팀 공통 지침', prompts: { ko: '팀 공통 지침' }, prompt_language: 'ko' };
      data = { team: state.team };
    } else return { ok: false, status: 404, json: async () => ({ error: '초대한 팀을 찾을 수 없습니다.' }) };
    return { ok: true, status: 200, json: async () => structuredClone(data) };
  };
  const React = require('react');
  const { createRoot } = require('react-dom/client');
  const compiled = { exports: {} };
  new Function('require', 'module', 'exports', source.outputFiles[0].text)(require, compiled, compiled.exports);
  const root = createRoot(document.getElementById('root'));
  await React.act(async () => root.render(React.createElement(compiled.exports.default)));
  const click = async (label) => {
    const button = [...document.querySelectorAll('button')].find((b) => b.textContent.trim() === label);
    assert.ok(button, `Button missing: ${label}`);
    assert.equal(button.disabled, false, label);
    await React.act(async () => button.click());
  };
  const fill = async (selector, value) => {
    const input = document.querySelector(selector);
    assert.ok(input, selector);
    await React.act(async () => {
      Object.getOwnPropertyDescriptor(Object.getPrototypeOf(input), 'value').set.call(input, value);
      input.dispatchEvent(new dom.window.Event('input', { bubbles: true }));
      input.dispatchEvent(new dom.window.Event('change', { bubbles: true }));
    });
  };
  return { state, click, fill, act: React.act, dom, close: async () => {
    await React.act(async () => root.unmount()); dom.window.close();
  } };
}
