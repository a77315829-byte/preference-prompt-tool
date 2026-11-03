import test from 'node:test';
import assert from 'node:assert/strict';
import { mount } from '../../../test-support/appHarness.js';
import { continuationRequest, handoffFileUrl, handoffLink, parseHandoffLink, readHandoffFile } from './handoffApi.js';

const initialBody = { purpose: '로그인 API 완성', progress: '라우트 구현 완료', remaining: '예외 응답과 테스트 추가', references: ['src/auth.py', 'https://example.test/spec'], prompt: 'Python으로 역할별 함수를 나눠 작성하라.' };
function handoffServer() {
  const state = { username: 'alice', loggedIn: true, records: [], history: new Map(), writes: 0, failSave: false, calls: [] };
  const response = (data, status = 200) => ({ ok: status < 400, status, json: async () => structuredClone(data) });
  const publicItem = (r) => ({ ...r, role: state.username === r.owner ? 'owner' : 'recipient',
    can_edit: (state.username === r.owner && ['draft', 'shared'].includes(r.status)) || (state.username === r.recipient && r.status === 'active'),
    can_share: state.username === r.owner && ['draft', 'shared'].includes(r.status), can_claim: state.username === r.recipient && r.status === 'shared',
    can_complete: state.username === r.recipient && r.status === 'active', can_reopen: state.username === r.recipient && r.status === 'done' });
  const remember = (r, event) => { state.history.set(r.id, [...(state.history.get(r.id) || []), { ...structuredClone(r), event, actor: state.username, saved_at: r.updated_at }]); };
  const fetch = async (path, options) => {
    const body = options.body ? JSON.parse(options.body) : {};
    if (path === '/api/auth/me') return response({ user: state.loggedIn ? { id: state.username === 'alice' ? 1 : 2, username: state.username } : null });
    if (path === '/api/auth/login') { state.loggedIn = true; state.username = body.username; return response({ user: { id: 2, username: state.username } }); }
    if (path === '/api/preferences') return response({ preferences: [{ id: 'pref', title: '내 Python 방식', domain_key: 'coding', revision: 1 }] });
    if (path === '/api/preferences/pref') return response({ preference: { id: 'pref', title: '내 Python 방식', domain_key: 'coding', revision: 1, prompt: initialBody.prompt, note: '' } });
    if (!path.startsWith('/api/handoffs')) return null;
    state.calls.push(path);
    if (!state.loggedIn) return response({ error: '로그인이 필요합니다.' }, 401);
    if (path === '/api/handoffs' && !options.method) return response({ handoffs: state.records.filter((r) => [r.owner, r.recipient].includes(state.username)).map(publicItem) });
    const bodyOf = () => Object.fromEntries(Object.keys(initialBody).map((key) => [key, body[key]]));
    if (path === '/api/handoffs' && options.method === 'POST') {
      if (state.failSave) return response({ error: '저장 실패 · 다시 확인해 주세요.' }, 409);
      state.writes += 1;
      const r = { id: state.writes.toString(16).padStart(32, '0'), title: body.title, body: bodyOf(), revision: 1, status: 'draft', owner: state.username,
        recipient: null, created_at: '2026-11-03T01:00:00Z', updated_at: '2026-11-03T01:00:00Z' };
      state.records.unshift(r); remember(r, 'created'); return response({ handoff: publicItem(r) }, 201);
    }
    const [, , , id, action, revision] = path.split('/');
    const r = state.records.find((row) => row.id === id && [row.owner, row.recipient].includes(state.username));
    if (!r) return response({ error: '이 계정에 공유되지 않았습니다.' }, 404);
    if (!action) return response({ handoff: publicItem(r) });
    if (action === 'history') {
      const history = state.history.get(id).filter((v) => state.username === r.owner || v.recipient === state.username);
      if (revision) return response({ snapshot: history.find((v) => v.revision === Number(revision)) });
      return response({ history: [...history].reverse() });
    }
    if (state.failSave || body.revision !== r.revision) return response({ error: '다른 팀원이 수정했습니다. 입력 내용을 보존하고 다시 확인해 주세요.' }, 409);
    if (action === 'share') { if (body.username === 'missing') return response({ error: '사용자가 없습니다.' }, 400); r.recipient = body.username; r.status = 'shared'; }
    if (action === 'claim' || action === 'reopen') r.status = 'active';
    if (action === 'complete') r.status = 'done';
    if (action === 'update') { r.body = { ...bodyOf(), attachments: r.body.attachments || [] }; r.title = body.title; }
    if (action === 'attach') r.body.attachments = [...(r.body.attachments || []), { id: 'f'.repeat(32), name: body.name, size: Buffer.from(body.data, 'base64').length, content_type: 'text/plain; charset=utf-8' }];
    if (action === 'detach') r.body.attachments = r.body.attachments.filter((f) => f.id !== body.fileId);
    r.revision += 1; state.writes += 1; remember(r, action);
    return response({ handoff: publicItem(r) });
  };
  return { state, fetch };
}

async function openNew(ui) {
  await ui.act(async () => document.querySelector('[aria-label="팀 업무 정리 선택"]').click());
  assert.ok(document.querySelector('.selection-button').textContent.includes('작업 인수인계 시작하기'));
  await ui.act(async () => document.querySelector('.selection-button').click());
  await ui.click('새 작업 넘기기');
}
async function fillWork(ui) {
  await ui.fill('#handoff-title', '로그인 작업');
  for (const [key, value] of Object.entries(initialBody)) await ui.fill(`#handoff-${key}`, Array.isArray(value) ? value.join('\n') : value);
}

test('목적·진행·자료·프롬프트 저장 → 특정 계정 공유·링크 전달 → 다음 사람 이어받기·수정·이전 기록', async () => {
  const api = handoffServer(); let ui = await mount('https://example.test/', 'coding', api.fetch);
  let link;
  try {
    await openNew(ui); await fillWork(ui); await ui.click('내 작업으로 저장');
    assert.equal(api.state.records[0].recipient, null);
    assert.equal(api.state.records[0].body.prompt, initialBody.prompt);
    await ui.fill('#handoff-recipient', 'missing'); await ui.click('이 팀원에게 공유');
    assert.ok(document.querySelector('[role="alert"]').textContent.includes('사용자가 없습니다'));
    await ui.fill('#handoff-recipient', 'bob'); await ui.click('이 팀원에게 공유');
    await ui.click('인수인계 링크 복사'); link = ui.state.copied;
    assert.ok(link.includes('?handoff=')); assert.equal(ui.state.sessions, 0);
    assert.equal(document.querySelectorAll('.nav-links button').length, 4);
  } finally { await ui.close(); }
  api.state.username = 'bob'; api.state.loggedIn = false;
  ui = await mount(link, 'coding', api.fetch);
  try {
    assert.ok(document.querySelector('.auth-embedded'));
    await ui.fill('#auth-username', 'bob'); await ui.fill('#auth-password', 'bob-password');
    await ui.act(async () => document.querySelector('.auth-form').dispatchEvent(new ui.dom.window.Event('submit', { bubbles: true, cancelable: true })));
    assert.equal(document.querySelector('#handoff-progress').readOnly, true);
    assert.equal(document.querySelector('#handoff-prompt').value, initialBody.prompt);
    await ui.click('이어서 맡기');
    assert.equal(document.querySelector('#handoff-progress').readOnly, false);
    await ui.fill('#handoff-progress', '예외 응답 처리 완료'); await ui.fill('#handoff-remaining', '테스트만 추가');
    const doneButton = [...document.querySelectorAll('button')].find((b) => b.textContent === '작업 완료로 표시');
    assert.equal(doneButton.disabled, true);
    await ui.click('변경 내용 저장'); await ui.click('맥락 + 프롬프트 복사');
    assert.ok(ui.state.copied.includes('예외 응답 처리 완료') && ui.state.copied.includes(initialBody.prompt));
    await ui.click('이전 기록 확인'); await ui.click('2번째 기록 보기');
    assert.equal(document.querySelector('#handoff-progress').value, initialBody.progress);
    assert.equal(document.querySelector('#handoff-progress').readOnly, true);
    assert.equal(document.querySelector('#handoff-recipient'), null);
    await ui.click('현재 작업으로 돌아가기');
    assert.equal(document.querySelector('#handoff-progress').value, '예외 응답 처리 완료');
    await ui.click('작업 완료로 표시'); assert.equal(document.querySelector('#handoff-progress').readOnly, true);
    await ui.click('다시 진행하기'); assert.equal(document.querySelector('#handoff-progress').readOnly, false);
  } finally { await ui.close(); }
});

test('저장 실패·버전 충돌에서 입력 보존, 이동 취소, 다른 계정 링크 거부', async () => {
  const api = handoffServer(); let ui = await mount('https://example.test/', 'coding', api.fetch);
  let id;
  try {
    await openNew(ui); await fillWork(ui); api.state.failSave = true; await ui.click('내 작업으로 저장');
    assert.equal(document.querySelector('#handoff-progress').value, initialBody.progress);
    api.state.failSave = false; await ui.click('내 작업으로 저장'); id = api.state.records[0].id;
    await ui.fill('#handoff-progress', '작성 중인 새 진행'); api.state.failSave = true; await ui.click('변경 내용 저장');
    assert.equal(document.querySelector('#handoff-progress').value, '작성 중인 새 진행');
    ui.dom.window.confirm = () => false; await ui.click('새 작업 넘기기');
    assert.equal(document.querySelector('#handoff-progress').value, '작성 중인 새 진행');
    ui.dom.window.confirm = () => true; await ui.click('새 작업 넘기기');
    assert.equal(document.querySelector('#handoff-title').value, '');
  } finally { await ui.close(); }
  api.state.username = 'carol'; ui = await mount(`https://example.test/?handoff=${id}`, 'coding', api.fetch);
  try {
    assert.ok(document.querySelector('[role="alert"]').textContent.includes('공유되지 않았습니다'));
    assert.equal(document.querySelector('#handoff-progress'), null);
  } finally { await ui.close(); }
});

test('보관함에서 선택한 지침과 개발 요청을 초안으로 가져오고 저장 전에는 공유하지 않는다', async () => {
  const api = handoffServer(); const ui = await mount('https://example.test/', 'coding', api.fetch);
  try {
    await ui.click('내 선호 보관함'); await ui.click('새 작업에 사용');
    await ui.fill('#preference-task', '토큰 갱신 API 구현');
    ui.dom.window.confirm = () => true;
    await ui.click('이 지침으로 작업 넘기기');
    assert.equal(document.querySelector('#handoff-prompt').value, initialBody.prompt);
    assert.equal(document.querySelector('#handoff-purpose').value, '토큰 갱신 API 구현');
    assert.equal(api.state.writes, 0);
    assert.equal(document.querySelector('#handoff-recipient'), null);
  } finally { await ui.close(); }
});

test('인수인계 링크는 다른 쿼리를 제거하고 맥락 요청문은 자료와 사용한 프롬프트를 포함한다', () => {
  const id = 'a'.repeat(32);
  assert.equal(handoffLink(id, 'https://example.test/?team=private#editor'), `https://example.test/?handoff=${id}`);
  assert.equal(parseHandoffLink(`https://example.test/?handoff=${id}`), id);
  assert.throws(() => parseHandoffLink('javascript:alert(1)'));
  const request = continuationRequest({ title: '작업', body: initialBody });
  assert.ok(request.startsWith(initialBody.prompt));
  for (const text of [initialBody.purpose, initialBody.progress, initialBody.remaining, ...initialBody.references]) assert.ok(request.includes(text));
});

async function selectFile(ui, content = '인수인계 파일 내용', name = '작업 메모.txt') {
  const file = new ui.dom.window.File([content], name, { type: 'text/plain' });
  await ui.act(async () => {
    const input = document.querySelector('#handoff-file');
    Object.defineProperty(input, 'files', { configurable: true, value: [file] });
    input.dispatchEvent(new ui.dom.window.Event('change', { bubbles: true }));
  });
  return file;
}
async function attachSelected(ui) {
  await ui.click('첨부 파일 저장');
  await ui.act(async () => { await new Promise((resolve) => setTimeout(resolve, 30)); });
}

test('실제 파일 선택·실패 재시도·공유 후 내려받기 링크·이전 첨부본 보존', async () => {
  const api = handoffServer(); let ui = await mount('https://example.test/', 'coding', api.fetch);
  let link;
  try {
    await openNew(ui); await fillWork(ui);
    assert.ok(document.querySelector('.handoff-attachments').textContent.includes('먼저 ‘내 작업으로 저장’'));
    await ui.click('내 작업으로 저장');
    await selectFile(ui); api.state.failSave = true; await attachSelected(ui);
    assert.ok(document.querySelector('[role="alert"]').textContent.includes('다른 팀원이 수정'));
    assert.ok(document.querySelector('.handoff-attachments').textContent.includes('아직 저장하지 않았어요'));
    api.state.failSave = false; await attachSelected(ui);
    assert.equal(api.state.records[0].body.attachments[0].name, '작업 메모.txt');
    assert.ok(document.querySelector('.handoff-attachments a[download]').href.includes('revision=2'));
    await ui.fill('#handoff-recipient', 'bob'); await ui.click('이 팀원에게 공유');
    await ui.click('인수인계 링크 복사'); link = ui.state.copied;
  } finally { await ui.close(); }
  api.state.username = 'bob'; ui = await mount(link, 'coding', api.fetch);
  try {
    assert.ok(document.querySelector('.handoff-attachments a[target="_blank"]').href.endsWith('revision=3&view=1'));
    assert.equal(document.querySelector('#handoff-file'), null);
    assert.equal(document.querySelector('#handoff-prompt').value, initialBody.prompt);
    assert.ok(document.querySelector('.handoff-references a').href.includes('example.test/spec'));
    await ui.click('이어서 맡기'); await ui.click('맥락 + 프롬프트 복사');
    assert.ok(ui.state.copied.includes('작업 메모.txt') && ui.state.copied.includes('내용은 이 요청문에 포함되지 않습니다'));
    const remove = document.querySelector('.handoff-attachments button');
    await ui.act(async () => remove.click());
    assert.equal(document.querySelector('.handoff-attachments a[download]'), null);
    await ui.click('이전 기록 확인'); await ui.click('3번째 기록 보기');
    assert.ok(document.querySelector('.handoff-attachments a[download]').href.endsWith('revision=3'));
    assert.equal(document.querySelector('#handoff-file'), null);
    assert.equal(api.state.records[0].body.attachments.length, 0);
  } finally { await ui.close(); }
});

test('저장 전 본문 변경·선택 파일 보존과 파일 크기 검증', async () => {
  const api = handoffServer(); const ui = await mount('https://example.test/', 'coding', api.fetch);
  try {
    await openNew(ui); await fillWork(ui); await ui.click('내 작업으로 저장');
    await selectFile(ui); await ui.fill('#handoff-progress', '새 진행 상황');
    let attach = [...document.querySelectorAll('button')].find((b) => b.textContent === '첨부 파일 저장');
    assert.equal(attach.disabled, true);
    await ui.click('변경 내용 저장');
    assert.ok(document.querySelector('.handoff-attachments').textContent.includes('작업 메모.txt'));
    await attachSelected(ui);
    assert.equal(api.state.records[0].body.progress, '새 진행 상황');
    assert.equal(api.state.records[0].body.attachments.length, 1);
    await selectFile(ui, '', 'empty.txt');
    attach = [...document.querySelectorAll('button')].find((b) => b.textContent === '첨부 파일 저장');
    assert.equal(attach.disabled, true);
    await assert.rejects(readHandoffFile({ size: 5 * 1024 * 1024 + 1 }), /5MB/);
    await ui.click('선택 취소');
    assert.equal(handoffFileUrl('a', 'b', 2, true), '/api/handoffs/a/files/b?revision=2&view=1');
    assert.equal(api.state.records[0].revision, 3);
  } finally { await ui.close(); }
});
