import test from 'node:test';
import assert from 'node:assert/strict';
import { composePreferenceRequest } from './preferenceText.js';

test('새 작업은 저장된 지침을 바꾸지 않고 별도 입력으로 이어 붙인다', () => {
  const prompt = '  짧게 요약하라.  ';
  assert.equal(composePreferenceRequest(prompt, ' 새 원문 ', 'summarization_ko'), '짧게 요약하라.\n\n---\n이번에 요약할 원문\n\n새 원문');
  assert.ok(composePreferenceRequest('코딩 지침', '기능 요청', 'coding').includes('이번 개발 요청\n\n기능 요청'));
  assert.equal(composePreferenceRequest(prompt, ' ', 'coding'), '');
  assert.equal(prompt, '  짧게 요약하라.  ');
});
