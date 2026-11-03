import test from 'node:test';
import assert from 'node:assert/strict';
import { mount } from '../../../test-support/appHarness.js';

const templates = [
  { id: 'meeting', category: '팀 업무', title: '회의에서 할 일 뽑기', description: '담당자와 기한', domain: 'summarization_ko', prompt: '회의에서 결정과 할 일을 정리하라.', personalizable: false },
  { id: 'bug', category: '코딩 도움', title: '재현 가능한 버그 보고', description: '재현 단계', domain: 'coding', prompt: '버그 관찰을 재현 단계로 정리하라.', personalizable: false },
  { id: 'summary', category: '문서 요약', title: '요약 방식', description: '문서 요약', domain: 'summarization', prompt: 'Summarize.', personalizable: true },
];
function server() {
  const state = { paidCalls: 0 };
  const response = (data) => ({ ok: true, status: 200, json: async () => structuredClone(data) });
  return { state, fetch: async (path) => {
    if (path === '/api/templates') return response({ templates });
    if (path === '/api/polish/checklist') return response({ checklist: [] });
    if (path === '/api/polish') { state.paidCalls += 1; return response({ checklist: [], revisedPrompt: '조건을 명시한 수정안', suggestions: '조건을 정리했습니다.' }); }
    return null;
  } };
}

test('세 번째 시작점은 팀 업무 템플릿으로 이동하고 검색·복사·지원 범위가 분명하다', async () => {
  const api = server(); const ui = await mount('https://example.test/', 'coding', api.fetch);
  try {
    assert.equal(document.querySelectorAll('.category-deck-dots button').length, 3);
    await ui.act(async () => document.querySelector('[aria-label="팀 업무 정리 선택"]').click());
    assert.ok(document.querySelector('.selection-button').textContent.includes('업무 템플릿 보기'));
    await ui.act(async () => document.querySelector('.selection-button').click());
    assert.equal(document.querySelectorAll('.template-card').length, 1);
    assert.ok(document.body.textContent.includes('회의에서 할 일 뽑기'));
    assert.equal([...document.querySelectorAll('button')].some((b) => b.textContent.trim() === '내 방식으로 바꾸기'), false);
    await ui.click('전체'); await ui.fill('#template-search', '버그');
    assert.equal(document.querySelectorAll('.template-card').length, 1);
    await ui.click('그대로 복사'); assert.equal(ui.state.copied, templates[1].prompt);
    assert.equal(api.state.paidCalls, 0);
    assert.equal(document.querySelectorAll('.nav-links button').length, 4);
  } finally { await ui.close(); }
});

test('요청문 점검은 템플릿 안에서 열고 명시적 실행 후 결과를 검토하며 입력 수정 시 초기화한다', async () => {
  const api = server(); const ui = await mount('https://example.test/', 'coding', api.fetch);
  try {
    await ui.click('템플릿'); await ui.click('팀 업무'); await ui.click('요청문 점검');
    assert.equal(document.querySelector('#polish-input').value, templates[0].prompt);
    assert.equal(api.state.paidCalls, 0);
    await ui.click('AI 수정안 만들기');
    assert.equal(api.state.paidCalls, 1);
    assert.ok(document.body.textContent.includes('조건을 명시한 수정안'));
    await ui.fill('#polish-input', '수정 중인 새 요청');
    assert.equal(document.body.textContent.includes('조건을 명시한 수정안'), false);
    await ui.click('요청문 점검 닫기');
    assert.equal(document.querySelector('#polish-input'), null);
    assert.equal(document.querySelectorAll('.template-card').length, 1);
  } finally { await ui.close(); }
});
