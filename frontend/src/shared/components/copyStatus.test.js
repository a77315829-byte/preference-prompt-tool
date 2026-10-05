import test from 'node:test';
import assert from 'node:assert/strict';
import {
  COPY_FAILED_NOTICE,
  IDLE_COPY_STATE,
  buttonLabel,
  copyResult,
  failedVariant,
  failureNotice,
} from './copyStatus.js';

test('실패 안내 문장이 정확하다', () => {
  assert.equal(COPY_FAILED_NOTICE, '복사하지 못했습니다. 내용을 직접 선택해 복사하세요');
});

test('대기 상태: 기본 문구이고 안내가 없다', () => {
  assert.equal(buttonLabel(IDLE_COPY_STATE, 'a', 'full'), '복사');
  assert.equal(buttonLabel(IDLE_COPY_STATE, 'a', 'compact'), '짧은 판 복사');
  assert.equal(failureNotice(IDLE_COPY_STATE, 'a'), '');
  assert.equal(failedVariant(IDLE_COPY_STATE, 'a'), '');
});

test('성공: 해당 버튼만 성공 문구, 안내 없음', () => {
  const s = copyResult('a', 'full', true);
  assert.equal(buttonLabel(s, 'a', 'full'), '복사했습니다 ✓');
  assert.equal(buttonLabel(s, 'a', 'compact'), '짧은 판 복사');
  assert.equal(failureNotice(s, 'a'), '');
});

test('성공: 짧은 판 버튼만 바뀐다', () => {
  const s = copyResult('a', 'compact', true);
  assert.equal(buttonLabel(s, 'a', 'compact'), '복사했습니다 ✓');
  assert.equal(buttonLabel(s, 'a', 'full'), '복사');
});

test('실패(일반): 버튼은 기본 문구, 안내가 보인다', () => {
  const s = copyResult('a', 'full', false);
  assert.equal(buttonLabel(s, 'a', 'full'), '복사');
  assert.equal(failureNotice(s, 'a'), '복사하지 못했습니다. 내용을 직접 선택해 복사하세요');
  assert.equal(failedVariant(s, 'a'), 'full');
});

test('실패(짧은 판): 기본 문구 유지, 짧은 판이 실패한 것으로 표시', () => {
  const s = copyResult('a', 'compact', false);
  assert.equal(buttonLabel(s, 'a', 'compact'), '짧은 판 복사');
  assert.equal(failedVariant(s, 'a'), 'compact');
  assert.equal(failureNotice(s, 'a'), COPY_FAILED_NOTICE);
});

test('다른 항목의 상태는 영향을 주지 않는다', () => {
  const failed = copyResult('a', 'full', false);
  assert.equal(failureNotice(failed, 'b'), '');
  assert.equal(failedVariant(failed, 'b'), '');
  const done = copyResult('a', 'full', true);
  assert.equal(buttonLabel(done, 'b', 'full'), '복사');
});

test('실패 뒤 같은 버튼이 성공하면 안내가 사라진다', () => {
  // 컴포넌트는 시도마다 상태를 copyResult 의 결과로 바꾼다. 실패 상태에서 출발해 전이를 본다.
  const failed = copyResult('a', 'full', false);
  assert.equal(failureNotice(failed, 'a'), COPY_FAILED_NOTICE);
  assert.equal(buttonLabel(failed, 'a', 'full'), '복사');

  const retried = copyResult('a', 'full', true);
  assert.equal(failureNotice(retried, 'a'), '');
  assert.equal(failedVariant(retried, 'a'), '');
  assert.equal(buttonLabel(retried, 'a', 'full'), '복사했습니다 ✓');
});

test('같은 입력이면 같은 출력이다', () => {
  const s = copyResult('a', 'full', false);
  assert.equal(failureNotice(s, 'a'), failureNotice(s, 'a'));
  assert.deepEqual(copyResult('a', 'full', false), copyResult('a', 'full', false));
});
