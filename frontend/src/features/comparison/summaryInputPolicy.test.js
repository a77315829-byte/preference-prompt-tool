import test from 'node:test';
import assert from 'node:assert/strict';
import { mount } from '../../../test-support/appHarness.js';
import { characterCount, sourceTooLong, isSummaryDomain } from './summaryInputPolicy.js';

test('summary policy counts code points including whitespace and applies only to summary domains', () => {
  assert.equal(characterCount(' 가🙂 '), 4);
  assert.equal(sourceTooLong('🙂'.repeat(12000)), false);
  assert.equal(sourceTooLong('🙂'.repeat(12000) + ' '), true);
  for (const domain of ['summarization', 'summarization_ko', 'summarization_hybrid']) assert.equal(isSummaryDomain(domain), true);
  for (const domain of ['coding', 'email', 'macsum_eval_agent']) assert.equal(isSummaryDomain(domain), false);
});

for (const domain of ['summarization', 'summarization_ko']) {
  test(`${domain}: oversized source stays editable and is never sent; boundary is sent without trimming`, async () => {
    const requests = [];
    const ui = await mount('https://example.test/?team=team-invited', domain, async (path, options) => {
      if (path !== '/api/sessions') return null;
      requests.push(JSON.parse(options.body));
      return { ok: false, status: 400, json: async () => ({ error: 'Test response' }) };
    });
    try {
      await ui.click('내 선호 고르기 시작');
      const selector = '.task-input';
      const findStart = () => [...document.querySelectorAll('button')].find(node => node.textContent.trim() === '이 내용으로 시작');
      const oversized = '🙂'.repeat(12000) + ' ';
      await ui.fill(selector, oversized);
      assert.equal(document.querySelector(selector).value, oversized);
      assert.equal(document.querySelector(selector).getAttribute('aria-invalid'), 'true');
      assert.equal(findStart().disabled, true);
      assert.match(document.querySelector('[role="alert"]').textContent, /12,001 \/ 12,000자/);
      await ui.act(async () => findStart().click());
      assert.equal(requests.length, 0);
      const boundary = ' ' + '🙂'.repeat(11998) + ' ';
      await ui.fill(selector, boundary);
      assert.equal(findStart().disabled, false);
      await ui.click('이 내용으로 시작');
      assert.equal(requests[0].sourceText, boundary);
      assert.equal(requests[0].domainKey, domain);
    } finally { await ui.close(); }
  });
}
