import test from 'node:test';
import assert from 'node:assert/strict';
import { mount } from '../../../test-support/appHarness.js';

const response = (data, status = 200) => ({ ok: status < 400, status, json: async () => structuredClone(data) });
const state = { session_id: 'private', domain_key: 'summarization_ko', source_text: '비공개 원문입니다. 중요한 수치가 있습니다.',
  total_rounds: 8, answered: 0, done: false, demo_mode: true, axes: [],
  pair: { pair_id: 'pair', a: { text: '비공개 비교 A', combo: { length: 'short' } }, b: { text: '비공개 비교 B', combo: { length: 'long' } } } };

for (const status of [401, 403, 404, 500]) {
  test(`비교 접근 오류 ${status}: 권한 오류만 지우고 일시 장애는 보존`, async () => {
    const ui = await mount('https://example.test/?team=team-invited', 'summarization_ko', async path => {
      if (path === '/api/sessions' || path === '/api/sessions/private') return response({ session: state });
      if (path === '/api/sessions/private/choices') return response({ error: '요청 실패' }, status);
      return null;
    });
    try {
      await ui.click('내 선호 고르기 시작');
      await ui.click('이 내용으로 시작');
      await ui.act(async () => document.querySelector('.comparison-option').click());
      if (status < 500) {
        assert.equal(document.querySelectorAll('.comparison-option').length, 0);
        assert.ok(!document.body.textContent.includes('비공개 비교 A'));
        assert.equal(document.querySelector('textarea').value, '');
        assert.match(document.body.textContent, /만료되었거나 접근할 수 없습니다/);
      } else {
        assert.equal(document.querySelectorAll('.comparison-option').length, 2);
        assert.match(document.body.textContent, /요청 실패/);
      }
    } finally { await ui.close(); }
  });
}

test('창으로 돌아오면 다른 탭 로그아웃을 확인하고 이전 내용을 지운다', async () => {
  let expired = false;
  const ui = await mount('https://example.test/?team=team-invited', 'summarization_ko', async path => {
    if (path === '/api/sessions') return response({ session: state });
    if (path === '/api/sessions/private') return expired ? response({ error: '만료' }, 404) : response({ session: state });
    return null;
  });
  try {
    await ui.click('내 선호 고르기 시작');
    await ui.click('이 내용으로 시작');
    expired = true;
    await ui.act(async () => window.dispatchEvent(new window.Event('focus')));
    assert.equal(document.querySelectorAll('.comparison-option').length, 0);
    assert.equal(document.querySelector('textarea').value, '');
  } finally { await ui.close(); }
});

test('서버 만료 시각에는 클릭 없이 비교·원문을 정리한다', async () => {
  const ui = await mount('https://example.test/?team=team-invited', 'summarization_ko', async path => {
    if (path === '/api/sessions' || path === '/api/sessions/private') return response({ session: { ...state, expires_in_seconds: 0.03 } });
    return null;
  });
  try {
    await ui.click('내 선호 고르기 시작');
    await ui.click('이 내용으로 시작');
    await ui.act(async () => new Promise(resolve => setTimeout(resolve, 80)));
    assert.equal(document.querySelectorAll('.comparison-option').length, 0);
    assert.equal(document.querySelector('textarea').value, '');
  } finally { await ui.close(); }
});

test('접근 차단 뒤 늦게 온 선택 응답이 화면을 복구하지 않는다', async () => {
  let resolveChoice;
  let expired = false;
  const ui = await mount('https://example.test/?team=team-invited', 'summarization_ko', async path => {
    if (path === '/api/sessions') return response({ session: state });
    if (path === '/api/sessions/private') return expired ? response({}, 404) : response({ session: state });
    if (path === '/api/sessions/private/choices') return new Promise(resolve => { resolveChoice = resolve; });
    return null;
  });
  try {
    await ui.click('내 선호 고르기 시작');
    await ui.click('이 내용으로 시작');
    await ui.act(async () => document.querySelector('.comparison-option').click());
    expired = true;
    await ui.act(async () => window.dispatchEvent(new window.Event('focus')));
    await ui.act(async () => resolveChoice(response({ session: { ...state, answered: 1 } })));
    assert.equal(document.querySelectorAll('.comparison-option').length, 0);
    assert.equal(document.querySelector('textarea').value, '');
  } finally { await ui.close(); }
});
