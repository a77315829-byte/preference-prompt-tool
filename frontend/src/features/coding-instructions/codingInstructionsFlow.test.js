import test from 'node:test';
import assert from 'node:assert/strict';
import { mount } from '../../../test-support/appHarness.js';

function codingServer({ loggedIn = true } = {}) {
  const state = { loggedIn, records: [], previews: [], writes: 0, failPreview: false, failSave: false };
  const response = (data, status = 200) => ({ ok: status < 400, status, json: async () => structuredClone(data) });
  const fetch = async (path, options) => {
    const body = options.body ? JSON.parse(options.body) : {};
    if (path === '/api/auth/me') return response({ user: state.loggedIn ? { id: 1, username: 'alice' } : null });
    if (path === '/api/auth/login') { state.loggedIn = true; return response({ user: { id: 1, username: 'alice' } }); }
    if (path === '/api/coding-instructions/preview') {
      state.previews.push(body.profile);
      if (state.failPreview) return response({ error: '지침을 만들지 못했어요.' }, 400);
      return response({ draft: { profile: body.profile, prompt: `개발 언어: ${body.profile.language}\n프레임워크: ${body.profile.framework}\n선호: ${JSON.stringify(body.profile.preferences)}\n${body.profile.extra}` } });
    }
    if (path === '/api/preferences' && options.method === 'POST') {
      if (state.failSave) return response({ error: '저장하지 못했어요.' }, 409);
      state.writes += 1;
      const item = { id: `p${state.writes}`, title: body.title, domain_key: body.domainKey, prompt: body.prompt, note: body.note,
        coding_profile: body.codingProfile, coding_profile_matches: true, revision: 1, created_at: '2026-11-03T01:00:00Z', updated_at: '2026-11-03T01:00:00Z' };
      state.records.unshift(item);
      return response({ preference: item }, 201);
    }
    if (path === '/api/preferences') return response({ preferences: state.records });
    const [, , , id, action] = path.split('/');
    const item = state.records.find((r) => r.id === id);
    if (item && !action) return response({ preference: item });
    if (item && action === 'update') {
      Object.assign(item, { prompt: body.prompt, title: body.title, note: body.note, revision: item.revision + 1, coding_profile_matches: false });
      return response({ preference: item });
    }
    return null;
  };
  return { state, fetch };
}

async function openCoding(ui) {
  await ui.act(async () => document.querySelector('[aria-label="코딩 도움 선택"]').click());
  await ui.act(async () => document.querySelector('.selection-button').click());
}

test('언어·프레임워크·선호로 지침 생성 → 복사·저장 → 새 작업 재사용·설정 재사용, 원본 유지', async () => {
  const api = codingServer(); const ui = await mount('https://example.test/', 'coding', api.fetch);
  try {
    await openCoding(ui);
    await ui.fill('#coding-framework', 'FastAPI');
    await ui.fill('#coding-choice-explanation', 'steps');
    await ui.fill('#coding-choice-structure', 'modular');
    await ui.fill('#coding-extra', '예외 처리 이유는 한국어로');
    await ui.click('내 설정으로 지침 만들기');
    assert.equal(ui.state.sessions, 0);
    assert.equal(api.state.previews[0].framework, 'FastAPI');
    assert.equal(api.state.previews[0].preferences.explanation, 'steps');
    await ui.click('지침 복사'); assert.ok(ui.state.copied.includes('Python'));
    await ui.fill('#save-preference-title', '내 Python 서버 방식');
    api.state.failSave = true; await ui.click('내 선호 보관함에 저장');
    assert.ok(document.querySelector('#coding-instructions-prompt').value.includes('FastAPI'));
    assert.equal(document.querySelector('#save-preference-title').value, '내 Python 서버 방식');
    api.state.failSave = false; await ui.click('내 선호 보관함에 저장');
    const original = structuredClone(api.state.records[0]);
    await ui.click('저장한 지침 열기');
    assert.ok(document.querySelector('.saved-coding-profile').textContent.includes('과정과 이유를 단계별로'));
    assert.equal(document.querySelector('#preference-team-invite'), null);
    await ui.click('예시 자료 넣어보기');
    assert.equal(document.querySelector('#preference-task').value.includes('React'), false);
    await ui.click('지침 + 새 작업 복사');
    assert.ok(ui.state.copied.includes(original.prompt));
    assert.deepEqual(api.state.records[0], original);
    ui.dom.window.confirm = () => false;
    await ui.click('이 설정으로 새 지침 만들기');
    assert.ok(document.querySelector('#preference-task'));
    ui.dom.window.confirm = () => true;
    await ui.click('이 설정으로 새 지침 만들기');
    assert.equal(document.querySelector('#coding-framework').value, 'FastAPI');
    assert.equal(document.querySelector('#coding-choice-explanation').value, 'steps');
    await ui.fill('#coding-language', 'Java');
    assert.equal(document.querySelector('#coding-framework').value, '');
    await ui.fill('#coding-framework', 'Spring Boot');
    await ui.click('내 설정으로 지침 만들기'); await ui.click('내 선호 보관함에 저장');
    assert.equal(api.state.records.length, 2);
    assert.deepEqual(api.state.records[1], original);
    assert.equal(api.state.records[0].coding_profile.language, 'Java');
  } finally { await ui.close(); }
});

test('직접 입력·빈 값 안내·생성 실패 보존과 설정 변경 시 이전 결과 무효화', async () => {
  const api = codingServer(); const ui = await mount('https://example.test/', 'coding', api.fetch);
  try {
    await openCoding(ui); await ui.fill('#coding-language', '__custom__');
    assert.equal([...document.querySelectorAll('button')].find((b) => b.textContent === '내 설정으로 지침 만들기').disabled, true);
    await ui.fill('#coding-language-custom', 'Elixir');
    await ui.fill('#coding-framework', '__custom__'); await ui.fill('#coding-framework-custom', 'Phoenix 1.x');
    api.state.failPreview = true; await ui.click('내 설정으로 지침 만들기');
    assert.equal(document.querySelector('#coding-language-custom').value, 'Elixir');
    assert.ok(document.querySelector('[role="alert"]'));
    api.state.failPreview = false; await ui.click('내 설정으로 지침 만들기');
    assert.ok(document.querySelector('#coding-instructions-prompt').value.includes('Phoenix 1.x'));
    await ui.fill('#coding-choice-comments', 'detailed');
    assert.equal(document.querySelector('#coding-instructions-prompt'), null);
    assert.equal(document.querySelector('#save-preference-title'), null);
    assert.equal(api.state.writes, 0);
  } finally { await ui.close(); }
});

test('익명으로 만든 설정·지침·이름은 로그인 중 유지되고 저장은 다시 눌러서 한다', async () => {
  const api = codingServer({ loggedIn: false }); const ui = await mount('https://example.test/', 'coding', api.fetch);
  try {
    await openCoding(ui); await ui.click('내 설정으로 지침 만들기');
    const prompt = document.querySelector('#coding-instructions-prompt').value;
    await ui.fill('#save-preference-title', '로그인 전 이름'); await ui.click('로그인하고 보관함에 저장');
    await ui.fill('#auth-username', 'alice'); await ui.fill('#auth-password', 'alice-password');
    await ui.act(async () => document.querySelector('.auth-form').dispatchEvent(new ui.dom.window.Event('submit', { bubbles: true, cancelable: true })));
    assert.equal(document.querySelector('#coding-instructions-prompt').value, prompt);
    assert.equal(document.querySelector('#save-preference-title').value, '로그인 전 이름');
    assert.equal(api.state.writes, 0);
    await ui.click('내 선호 보관함에 저장'); await ui.click('저장한 지침 열기');
    await ui.click('지침 수정'); await ui.fill('#preference-prompt', '직접 바꾼 지침'); await ui.click('변경 내용 저장');
    assert.ok(document.querySelector('.saved-coding-profile').textContent.includes('처음 저장한 설정'));
  } finally { await ui.close(); }
});

test('기존 React 예시 비교 진입·선택·결과는 유지하고 설정 경로와 오갈 수 있다', async () => {
  const api = codingServer(); const ui = await mount('https://example.test/', 'coding', api.fetch);
  try {
    await openCoding(ui); await ui.click('React 예시 비교로 취향 찾기');
    assert.ok(document.querySelector('#coding-task'));
    await ui.click('다른 언어·프레임워크로 지침 만들기');
    assert.ok(document.querySelector('#coding-language'));
    await ui.click('React 예시 비교로 취향 찾기'); await ui.click('이 내용으로 시작');
    await ui.act(async () => document.querySelector('[aria-label^="예시 A 선택"]').click());
    assert.equal(ui.state.sessions, 1);
    assert.ok(document.body.textContent.includes('나만의 코딩 프롬프트가 완성됐어요'));
  } finally { await ui.close(); }
});
