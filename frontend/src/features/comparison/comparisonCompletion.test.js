import test from 'node:test';
import assert from 'node:assert/strict';
import { mount } from '../../../test-support/appHarness.js';

for (const [reason, message] of [
  ['selection_resolved', '4회에서 자동으로 마쳤어요'],
  ['no_more_pairs', '선호가 정해지지 않은 항목은 미정으로 남깁니다'],
  ['round_limit', '모든 선호가 확정됐다는 뜻은 아니에요'],
]) {
  test(`요약 마지막 응답 뒤 자동으로 결과와 종료 이유 표시: ${reason}`, async () => {
    const session = { session_id: 'summary', domain_key: 'summarization_ko', source_text: '문장입니다. '.repeat(20),
      total_rounds: 6, round_limit: 6, answered: 3, done: false, demo_mode: true, axes: [],
      pair: { pair_id: 'last', a: { text: '짧은 요약', combo: { length: 'short' } }, b: { text: '긴 요약', combo: { length: 'long' } } } };
    const response = data => ({ ok: true, status: 200, json: async () => structuredClone(data) });
    const ui = await mount('https://example.test/?team=team-invited', 'summarization_ko', async path => {
      if (path === '/api/sessions') return response({ session });
      if (path === '/api/sessions/summary/choices') return response({ session: { ...session, done: true, answered: 4,
        total_rounds: 4, pair: null, completion_reason: reason, prompt: '요약 지침',
        prompts: { ko: '요약 지침' }, prompt_language: 'ko', exports: [] } });
      return null;
    });
    try {
      await ui.click('내 선호 고르기 시작');
      assert.match(document.querySelector('.comparison-source-hint').textContent, /최대 8회/);
      await ui.click('이 내용으로 시작');
      assert.match(document.querySelector('.comparison-progress').textContent, /3회 완료 · 최대 6회/);
      await ui.act(async () => document.querySelector('.comparison-option').click());
      assert.equal(document.querySelectorAll('.comparison-option').length, 0);
      assert.match(document.body.textContent, /나만의 요약 프롬프트가 완성됐어요/);
      assert.match(document.querySelector('.comparison-progress').textContent, /4회 비교로 마침/);
      assert.ok(document.body.textContent.includes(message));
      if (reason !== 'selection_resolved') assert.ok(!document.body.textContent.includes('현재 선택에서 더 구분할 항목이 없어'));
    } finally { await ui.close(); }
  });
}
