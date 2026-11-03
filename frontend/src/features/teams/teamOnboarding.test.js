import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { build } from 'esbuild';
import { JSDOM } from 'jsdom';

// 실제 화면과 상태 전환을 검사한다. 애니메이션과 HTTP만 대체한다.
const source = await build({
  entryPoints: [fileURLToPath(new URL('../../app/App.jsx', import.meta.url))],
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

async function mount(url, invitedDomain = 'coding') {
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
      Object.getOwnPropertyDescriptor(dom.window.HTMLInputElement.prototype, 'value').set.call(input, value);
      input.dispatchEvent(new dom.window.Event('input', { bubbles: true }));
    });
  };
  return { state, click, fill, act: React.act, dom, close: async () => {
    await React.act(async () => root.unmount()); dom.window.close();
  } };
}

test('팀 만들기 → 초대 복사 → 비교 → 이름 확인 → 명시적으로 선호 합치기', async () => {
  const ui = await mount('https://example.test/');
  try {
    await ui.click('팀 만들기 · 초대로 참여');
    await ui.fill('#new-team-name', '우리 프론트엔드팀');
    await ui.act(async () => document.querySelector('form').dispatchEvent(new ui.dom.window.Event('submit', { bubbles: true, cancelable: true })));
    assert.equal(ui.state.creates, 1);
    assert.equal(ui.state.sessions, 0);
    await ui.click('초대 링크 복사');
    assert.equal(ui.state.copied, 'https://example.test/?team=team-invited');
    await ui.click('내 선호 고르기 시작');
    assert.ok(document.body.textContent.includes('우리 프론트엔드팀 · 2. 내 선호 고르기'));
    await ui.click('이 내용으로 시작');
    await ui.act(async () => document.querySelector('[aria-label^="예시 A 선택"]').click());
    assert.equal(ui.state.merges, 0);
    const merge = [...document.querySelectorAll('button')].find((b) => b.textContent === '내 선호를 팀 기준에 합치기');
    assert.equal(merge.disabled, true);
    await ui.fill('[aria-label="내 이름"]', '민수');
    await ui.click('내 선호를 팀 기준에 합치기');
    assert.equal(ui.state.merges, 1);
    assert.ok(document.body.textContent.includes('반영 완료'));
    await ui.click('팀 안내와 초대로 돌아가기');
    assert.ok(document.body.textContent.includes('선호를 합친 팀원 1명'));
  } finally { await ui.close(); }
});

test('초대 링크는 바로 팀을 확인하고, 요약 언어를 바꿔 다른 기준에 합치지 않는다', async () => {
  const ui = await mount('https://example.test/?team=team-invited', 'summarization_ko');
  try {
    assert.ok(document.body.textContent.includes('함께 개발팀'));
    assert.equal(ui.state.creates, 0);
    assert.equal(ui.state.sessions, 0);
    await ui.click('내 선호 고르기 시작');
    assert.equal(document.querySelector('[aria-label="요약 언어"]'), null);
    await ui.click('이 내용으로 시작');
    assert.equal(ui.state.sessions, 1);
  } finally { await ui.close(); }
});

test('없는 팀 초대는 오류를 알리고 새 팀을 임의로 만들지 않는다', async () => {
  const ui = await mount('https://example.test/?team=missing-team');
  try {
    assert.ok(document.querySelector('[role="alert"]').textContent.includes('팀을 찾을 수 없습니다'));
    assert.equal(ui.state.creates, 0);
    assert.equal(ui.state.sessions, 0);
    assert.equal([...document.querySelectorAll('button')].some((b) => b.textContent === '내 선호 고르기 시작'), false);
  } finally { await ui.close(); }
});
