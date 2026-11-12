import test from 'node:test';
import assert from 'node:assert/strict';
import { mount } from '../../../test-support/appHarness.js';

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
