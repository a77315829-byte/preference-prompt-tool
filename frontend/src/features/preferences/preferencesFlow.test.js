import test from 'node:test';
import assert from 'node:assert/strict';
import { mount } from '../../../test-support/appHarness.js';

function shelfServer({ loggedIn = true, live = false } = {}) {
  const state = { loggedIn, records: [], writes: 0, runs: 0, deletes: 0, failSave: false,
    teamDomain: 'coding', teamSnapshot: 'team-v1', lastRun: null, recognized: true, failCompose: false };
  const response = (data, status = 200) => ({ ok: status < 400, status, json: async () => structuredClone(data) });
  const fetch = async (path, options) => {
    const body = options.body ? JSON.parse(options.body) : {};
    if (path === '/api/auth/me') return response({ user: state.loggedIn ? { id: 1, username: 'alice' } : null, signupOpen: true });
    if (path === '/api/auth/login') { state.loggedIn = true; return response({ user: { id: 1, username: 'alice' } }); }
    if (path === '/api/auth/logout') { state.loggedIn = false; return response({ user: null }); }
    if (path === '/api/health') return response({ live, liveConfigured: live });
    if (path === '/api/teams') return response({ teams: [{ code: 'devteam', name: '함께 개발팀', domain_key: state.teamDomain }] });
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
    if (action === 'compare-team') {
      if (item.domain_key !== state.teamDomain) return response({ error: '같은 종류의 지침끼리 비교해 주세요.' }, 400);
      return response({ comparison: {
        preference_id: id, revision: item.revision, team_code: body.teamCode, team_name: '함께 개발팀', domain_key: item.domain_key,
        team_members: 3, personal_recognized: state.recognized, team_prompt: '팀 기준의 지침', comparison_prompt: '팀 기준의 비교용 문장',
        team_snapshot: state.teamSnapshot, team_language: 'ko', languages: ['ko', 'en'],
        axes: [{ axis: 'code_structure', label: '코드 구성', personal_value: 'compact', team_value: 'separated',
          status: 'different', team_agreed: false, team_tied: false, team_votes: { separated: 2, compact: 1 } },
        { axis: 'type_detail', label: '타입 작성', personal_value: 'explicit', team_value: 'inferred', status: 'different', team_agreed: true, team_votes: { inferred: 3 } }],
      } });
    }
    if (action === 'compose-task') {
      if (state.failCompose || body.teamSnapshot !== state.teamSnapshot) return response({ error: '팀 기준이 바뀌었습니다. 새로 확인해 주세요.' }, 409);
      assert.ok(['personal', 'team'].includes(body.choices.code_structure));
      assert.ok(['personal', 'team'].includes(body.choices.type_detail));
      return response({ draft: { prompt: `작업용: ${body.choices.code_structure} 구성 / ${body.choices.type_detail} 타입`,
        choices: body.choices, snapshot: JSON.stringify(body.choices) + state.teamSnapshot } });
    }
    if (action === 'save-task') {
      if (state.failSave || body.teamSnapshot !== state.teamSnapshot) return response({ error: '팀 기준이 바뀌었습니다. 다시 확인해 주세요.' }, 409);
      assert.equal(body.taskSnapshot, JSON.stringify(body.choices) + state.teamSnapshot);
      return fetch('/api/preferences', { method: 'POST', body: JSON.stringify({ title: body.title, note: body.note,
        domainKey: item.domain_key, prompt: `작업용: ${body.choices.code_structure} 구성 / ${body.choices.type_detail} 타입` }) });
    }
    if (action === 'update') {
      if (state.failSave) return response({ error: '다른 창에서 수정된 항목입니다. 다시 열어 주세요.' }, 409);
      Object.assign(item, { title: body.title, domain_key: body.domainKey, prompt: body.prompt, note: body.note, revision: item.revision + 1 });
      return response({ preference: item });
    }
    if (action === 'run') {
      if (body.basis !== 'personal' && body.teamSnapshot !== state.teamSnapshot) return response({ error: '팀 기준이 바뀌었습니다. 새로 확인해 주세요.' }, 409);
      state.runs += 1;
      state.lastRun = body;
      assert.equal(body.revision, item.revision);
      return response({ output: '새 작업의 실행 결과', model: 'test-model', revision: item.revision, preference_id: item.id,
        basis: body.basis || 'personal', team_snapshot: body.teamSnapshot || null, task_snapshot: body.taskSnapshot || null });
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

test('기준 차이 확인 → 팀용·개인용 전환 → 복사·실행 → 바뀐 팀 기준 다시 확인', async () => {
  const api = shelfServer({ live: true });
  const ui = await mount('https://example.test/', 'coding', api.fetch);
  try {
    await finishCoding(ui);
    await ui.click('내 선호 보관함에 저장');
    await ui.click('저장한 지침 열기');
    await ui.fill('#preference-task', '새 개발 요청');
    await ui.fill('#preference-team-list', 'devteam');
    await ui.click('개인·팀 기준 비교하기');
    const row = document.querySelector('.preference-comparison-table tbody tr');
    assert.ok(row.textContent.includes('간결하게 작성'));
    assert.ok(row.textContent.includes('역할별 파일로 분리'));
    assert.ok(row.textContent.includes('다름') && row.textContent.includes('팀 합의 필요'));
    await ui.click('팀용으로 사용');
    await ui.click('지침 + 새 작업 복사');
    assert.ok(ui.state.copied.includes('팀 기준의 지침'));
    assert.equal(ui.state.copied.includes('팀 기준의 비교용 문장'), false);
    await ui.click('이 지침으로 AI 실행');
    assert.equal(api.state.lastRun.basis, 'team');
    assert.equal(api.state.lastRun.teamSnapshot, 'team-v1');
    await ui.click('개인용으로 사용');
    assert.ok(document.body.textContent.includes('이전 입력·지침으로 실행한 결과'));
    await ui.click('지침 + 새 작업 복사');
    assert.ok(ui.state.copied.includes('개인 지침'));
    assert.equal(api.state.records[0].prompt, '개인 지침');
    await ui.click('팀용으로 사용');
    api.state.teamSnapshot = 'team-v2';
    await ui.click('이 지침으로 AI 실행');
    assert.ok(document.querySelector('[role="alert"]').textContent.includes('팀 기준이 바뀌'));
    assert.equal(api.state.runs, 1);
    await ui.click('팀 기준 새로 확인');
    await ui.click('팀용으로 사용');
    await ui.click('이 지침으로 AI 실행');
    assert.equal(api.state.lastRun.teamSnapshot, 'team-v2');
    assert.equal(api.state.records[0].revision, 1);
  } finally { await ui.close(); }
});

test('다른 팀으로 바꾸다 비교가 실패하면 이전 팀용을 사용할 수 없고 작업은 유지한다', async () => {
  const api = shelfServer();
  const ui = await mount('https://example.test/', 'coding', api.fetch);
  try {
    await finishCoding(ui);
    await ui.click('내 선호 보관함에 저장');
    await ui.click('저장한 지침 열기');
    await ui.fill('#preference-task', '유지할 개발 요청');
    await ui.fill('#preference-team-invite', 'devteam');
    await ui.click('개인·팀 기준 비교하기');
    await ui.click('팀용으로 사용');
    api.state.teamDomain = 'summarization_ko';
    await ui.fill('#preference-team-invite', 'another-team');
    await ui.click('개인·팀 기준 비교하기');
    assert.ok(document.querySelector('[role="alert"]').textContent.includes('같은 종류'));
    const teamButton = [...document.querySelectorAll('button')].find((b) => b.textContent === '팀용으로 사용');
    assert.equal(teamButton.disabled, true);
    assert.equal(document.querySelector('#preference-task').value, '유지할 개발 요청');
    await ui.click('지침 + 새 작업 복사');
    assert.ok(ui.state.copied.includes('개인 지침'));
  } finally { await ui.close(); }
});

test('항목별 선택 → 작업용 만들기 → 복사·실행 → 선택 수정·기준 갱신 시 이전 작업용 해제', async () => {
  const api = shelfServer({ live: true });
  const ui = await mount('https://example.test/', 'coding', api.fetch);
  const choose = async (axis, source) => ui.act(async () => document.querySelector(`input[name="task-choice-${axis}"][value="${source}"]`).click());
  const button = (name) => [...document.querySelectorAll('button')].find((b) => b.textContent === name);
  try {
    await finishCoding(ui);
    await ui.click('내 선호 보관함에 저장');
    await ui.click('저장한 지침 열기');
    await ui.fill('#preference-task', '계속 유지할 작업');
    await ui.fill('#preference-team-list', 'devteam');
    await ui.click('개인·팀 기준 비교하기');
    assert.equal(button('이번 작업용 만들기').disabled, true);
    await choose('code_structure', 'team');
    assert.equal(button('이번 작업용 만들기').disabled, true);
    await choose('type_detail', 'personal');
    await ui.click('이번 작업용 만들기');
    assert.equal(button('이번 작업용으로 사용').getAttribute('aria-pressed'), 'true');
    await ui.click('지침 + 새 작업 복사');
    assert.ok(ui.state.copied.includes('작업용: team 구성 / personal 타입'));
    assert.ok(ui.state.copied.includes('계속 유지할 작업'));
    await ui.click('이 지침으로 AI 실행');
    assert.equal(api.state.lastRun.basis, 'custom');
    assert.deepEqual(api.state.lastRun.choices, { code_structure: 'team', type_detail: 'personal' });
    assert.ok(document.body.textContent.includes('이번 작업용 지침'));
    await ui.click('개인용으로 사용');
    await ui.click('이번 작업용으로 사용');
    await choose('code_structure', 'personal');
    assert.equal(button('이번 작업용으로 사용').disabled, true);
    assert.ok(document.body.textContent.includes('이전 입력·지침으로 실행한 결과'));
    api.state.failCompose = true;
    await ui.click('이번 작업용 만들기');
    assert.ok(document.querySelector('[role="alert"]').textContent.includes('팀 기준이 바뀌'));
    assert.equal(button('이번 작업용으로 사용').disabled, true);
    api.state.failCompose = false;
    await ui.click('팀 기준 새로 확인');
    assert.equal(document.querySelector('input[name="task-choice-code_structure"]:checked'), null);
    assert.equal(document.querySelector('#preference-task').value, '계속 유지할 작업');
    assert.equal(api.state.records[0].prompt, '개인 지침');
    assert.equal(api.state.records[0].revision, 1);
    assert.equal(api.state.writes, 1);
  } finally { await ui.close(); }
});

test('항목을 확정할 수 없는 수정 지침은 조합 제한 이유와 전체 선택을 안내한다', async () => {
  const api = shelfServer(); api.state.recognized = false;
  const ui = await mount('https://example.test/', 'coding', api.fetch);
  try {
    await finishCoding(ui); await ui.click('내 선호 보관함에 저장'); await ui.click('저장한 지침 열기');
    await ui.fill('#preference-team-list', 'devteam'); await ui.click('개인·팀 기준 비교하기');
    assert.ok(document.querySelector('.task-preference-mixer').textContent.includes('항목을 정확히 구분할 수 없어'));
    assert.equal(document.querySelector('input[name^="task-choice-"]'), null);
    await ui.click('팀용으로 사용');
  } finally { await ui.close(); }
});

test('작업용 이름·설명으로 새로 저장 → 현재 작업 유지 → 새 항목 열어 다음 작업에 재사용', async () => {
  const api = shelfServer({ live: true });
  const ui = await mount('https://example.test/', 'coding', api.fetch);
  ui.dom.window.confirm = () => true;
  const choose = async (axis, source) => ui.act(async () => document.querySelector(`input[name="task-choice-${axis}"][value="${source}"]`).click());
  try {
    await finishCoding(ui); await ui.click('내 선호 보관함에 저장'); await ui.click('저장한 지침 열기');
    await ui.fill('#preference-task', '저장하지 않을 이번 작업');
    await ui.fill('#preference-team-list', 'devteam'); await ui.click('개인·팀 기준 비교하기');
    assert.equal(document.querySelector('#save-task-preference-title'), null);
    await choose('code_structure', 'team'); await choose('type_detail', 'personal'); await ui.click('이번 작업용 만들기');
    await ui.fill('#save-task-preference-title', '팀 구성과 내 타입 방식');
    await ui.fill('#save-task-preference-note', '새 React 기능에 쓰기');
    api.state.failSave = true;
    await ui.click('작업용 지침을 새 항목으로 저장');
    assert.ok(document.querySelector('[role="alert"]').textContent.includes('팀 기준이 바뀌'));
    assert.equal(document.querySelector('#save-task-preference-title').value, '팀 구성과 내 타입 방식');
    assert.equal(api.state.writes, 1);
    api.state.failSave = false;
    await ui.click('작업용 지침을 새 항목으로 저장');
    assert.equal(api.state.writes, 2);
    assert.equal(api.state.records[0].title, '팀 구성과 내 타입 방식');
    assert.equal(api.state.records[0].note, '새 React 기능에 쓰기');
    assert.equal(api.state.records[0].prompt, '작업용: team 구성 / personal 타입');
    assert.equal(Object.hasOwn(api.state.records[0], 'task'), false);
    assert.equal(api.state.records[1].prompt, '개인 지침');
    assert.equal(api.state.records[1].revision, 1);
    assert.equal(document.querySelector('#preference-task').value, '저장하지 않을 이번 작업');
    const savedButton = [...document.querySelectorAll('button')].find((b) => b.textContent === '새 항목으로 저장했어요');
    assert.equal(savedButton.disabled, true);
    assert.equal(document.querySelectorAll('.preference-list li').length, 2);
    await ui.click('저장한 작업용 열기');
    assert.equal(document.querySelector('#preference-task').value, '');
    assert.equal(document.querySelector('.preference-editor h3').textContent, '팀 구성과 내 타입 방식 · 새 작업에 사용하기');
    await ui.fill('#preference-task', '다음 작업'); await ui.click('지침 + 새 작업 복사');
    assert.ok(ui.state.copied.includes('작업용: team 구성 / personal 타입'));
    assert.ok(ui.state.copied.includes('다음 작업'));
    assert.equal(ui.state.copied.includes('저장하지 않을 이번 작업'), false);
    await ui.click('이 지침으로 AI 실행');
    assert.equal(api.state.lastRun.basis, 'personal');
    assert.equal(api.state.lastRun.task, '다음 작업');
  } finally { await ui.close(); }
});
