import test from 'node:test';
import assert from 'node:assert/strict';
import { mount } from '../../../test-support/appHarness.js';

function shelfServer({ loggedIn = true, live = false } = {}) {
  const state = { loggedIn, records: [], writes: 0, runs: 0, deletes: 0, failSave: false };
  const response = (data, status = 200) => ({ ok: status < 400, status, json: async () => structuredClone(data) });
  const fetch = async (path, options) => {
    const body = options.body ? JSON.parse(options.body) : {};
    if (path === '/api/auth/me') return response({ user: state.loggedIn ? { id: 1, username: 'alice' } : null, signupOpen: true });
    if (path === '/api/auth/login') { state.loggedIn = true; return response({ user: { id: 1, username: 'alice' } }); }
    if (path === '/api/auth/logout') { state.loggedIn = false; return response({ user: null }); }
    if (path === '/api/health') return response({ live, liveConfigured: live });
    if (!path.startsWith('/api/preferences')) return null;
    if (!state.loggedIn) return response({ error: '로그인이 필요합니다.' }, 401);
    if (path === '/api/preferences' && !options.method) return response({ preferences: state.records });
    if (path === '/api/preferences' && options.method === 'POST') {
      state.writes += 1;
      const item = { id: `saved-${state.writes}`, title: body.title, domain_key: body.domainKey, prompt: body.prompt, note: body.note || '',
        revision: 1, created_at: '2026-11-03T00:00:00Z', updated_at: '2026-11-03T00:00:00Z' };
      state.records.unshift(item);
      return response({ preference: item }, 201);
    }
    const [, , , id, action] = path.split('/');
    const item = state.records.find((p) => p.id === id);
    if (!item) return response({ error: '찾을 수 없습니다.' }, 404);
    if (!action) return response({ preference: item });
    if (action === 'update') {
      if (state.failSave) return response({ error: '다른 창에서 수정된 항목입니다. 다시 열어 주세요.' }, 409);
      Object.assign(item, { title: body.title, domain_key: body.domainKey, prompt: body.prompt, note: body.note, revision: item.revision + 1 });
      return response({ preference: item });
    }
    if (action === 'run') {
      state.runs += 1;
      assert.equal(body.revision, item.revision);
      return response({ output: '새 작업의 실행 결과', model: 'test-model', revision: item.revision, preference_id: item.id });
    }
    if (action === 'delete') {
      state.deletes += 1; state.records = state.records.filter((p) => p.id !== id);
      return response({ ok: true });
    }
    return response({ error: '알 수 없는 경로' }, 404);
  };
  return { state, fetch };
}

async function finishCoding(ui) {
  await ui.click('내 선호 보관함');
  await ui.click('코딩 취향 찾기');
  await ui.click('이 내용으로 시작');
  await ui.act(async () => document.querySelector('[aria-label^="예시 A 선택"]').click());
}

test('비교 결과 저장 → 수정 → 새 요청에 복사·실행 → 다시 열기', async () => {
  const api = shelfServer({ live: true });
  const ui = await mount('https://example.test/', 'coding', api.fetch);
  ui.dom.window.confirm = () => true;
  try {
    await finishCoding(ui);
    await ui.fill('#save-preference-title', '내 React 방식');
    await ui.click('내 선호 보관함에 저장');
    assert.equal(api.state.records[0].prompt, '개인 지침');
    assert.equal(Object.hasOwn(api.state.records[0], 'source_text'), false);
    await ui.click('저장한 지침 열기');
    await ui.fill('#preference-task', '새로운 검색 화면을 만들어 주세요.');
    await ui.click('지침 + 새 작업 복사');
    assert.ok(ui.state.copied.includes('개인 지침'));
    assert.ok(ui.state.copied.includes('새로운 검색 화면'));
    assert.equal(api.state.records[0].prompt, '개인 지침');
    await ui.click('지침 수정');
    await ui.fill('#preference-prompt', '수정한 코딩 지침');
    await ui.click('변경 내용 저장');
    assert.equal(api.state.records[0].revision, 2);
    await ui.click('새 작업에 쓰기');
    await ui.click('이 지침으로 AI 실행');
    assert.equal(api.state.runs, 1);
    assert.equal(document.querySelector('[aria-label="AI 실행 결과 내용"]').value, '새 작업의 실행 결과');
    await ui.fill('#preference-task', '다른 작업');
    assert.ok(document.body.textContent.includes('이전 입력·지침으로 실행한 결과'));
    await ui.click('시작하기');
    await ui.click('내 선호 보관함');
    await ui.click('새 작업에 사용');
    assert.ok(document.body.textContent.includes('수정한 코딩 지침'));
    assert.equal(document.querySelector('#preference-task').value, '');
  } finally { await ui.close(); }
});

test('결과 화면에서 로그인해도 제목·프롬프트가 유지되고 저장은 명시적으로 한다', async () => {
  const api = shelfServer({ loggedIn: false });
  const ui = await mount('https://example.test/', 'coding', api.fetch);
  try {
    await finishCoding(ui);
    await ui.fill('#save-preference-title', '로그인 전 정한 이름');
    await ui.click('로그인하고 보관함에 저장');
    await ui.fill('#auth-username', 'alice');
    await ui.fill('#auth-password', 'alice-password');
    await ui.act(async () => document.querySelector('.auth-form').dispatchEvent(new ui.dom.window.Event('submit', { bubbles: true, cancelable: true })));
    assert.equal(document.querySelector('#save-preference-title').value, '로그인 전 정한 이름');
    assert.equal(api.state.writes, 0);
    await ui.click('내 선호 보관함에 저장');
    assert.equal(api.state.records[0].title, '로그인 전 정한 이름');
  } finally { await ui.close(); }
});

test('빈 보관함 안내·직접 추가·저장 실패 보존·삭제 확인·로그아웃', async () => {
  const api = shelfServer();
  const ui = await mount('https://example.test/', 'coding', api.fetch);
  try {
    await ui.click('내 선호 보관함');
    assert.ok(document.body.textContent.includes('아직 저장한 지침이 없어요'));
    await ui.click('가진 프롬프트 직접 추가');
    await ui.fill('#preference-title', '내 요약');
    await ui.fill('#preference-prompt', '짧게 요약해 주세요.');
    await ui.click('변경 내용 저장');
    await ui.fill('#preference-note', '수정 중인 설명');
    api.state.failSave = true;
    await ui.click('변경 내용 저장');
    assert.equal(document.querySelector('#preference-note').value, '수정 중인 설명');
    assert.ok(document.querySelector('[role="alert"]').textContent.includes('다른 창'));
    ui.dom.window.confirm = () => false;
    await ui.click('보관함에서 삭제');
    assert.equal(api.state.deletes, 0);
    ui.dom.window.confirm = () => true;
    await ui.click('보관함에서 삭제');
    assert.equal(api.state.deletes, 1);
    await ui.click('로그아웃');
    assert.equal(document.querySelector('#preference-prompt'), null);
    assert.ok(document.querySelector('.auth-embedded'));
  } finally { await ui.close(); }
});
