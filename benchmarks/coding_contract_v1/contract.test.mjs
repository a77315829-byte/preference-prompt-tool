import test from 'node:test';
import assert from 'node:assert/strict';
import { buildPrompt, inspectReply } from './contract.mjs';

const code = 'export function Counter() { return <button>0</button>; }';
const markdown = (source = code, notes = '') => `### Component.tsx\n\`\`\`tsx\n${source}\n\`\`\`\n${notes}`;
const profile = { explanation: 'brief', delivery: 'markdown' };

for (const explanation of ['none', 'brief', 'steps']) {
  for (const delivery of ['markdown', 'json']) {
    test(`지정한 형식을 검사: ${explanation}/${delivery}`, () => {
      const items = explanation === 'none' ? [] : explanation === 'brief' ? ['Counter 사용 방법.'] : ['상태 준비.', '버튼 렌더링.', '동작 확인.'];
      const reply = delivery === 'json' ? JSON.stringify({ files: { 'Component.tsx': code }, explanation: items })
        : markdown(code, items.map((item, i) => `${explanation === 'steps' ? `${i + 1}.` : '-'} ${item}`).join('\n'));
      const report = inspectReply(reply, { explanation, delivery });
      assert.equal(report.contractSatisfied, true);
      assert.equal(report.functionalCorrectness, 'not_run');
      assert.equal(report.typeCorrectness, 'not_run');
      assert.equal(report.jointSuccess, null);
      assert.ok(buildPrompt({ explanation, delivery }).includes('이번 작업'));
    });
  }
}

test('설명 형식, 항목 수, 코드 밖 추가 블록을 각각 거절한다', () => {
  for (const notes of ['번호 없는 문단', '- 하나\n- 둘\n- 셋\n- 넷', '- 하나\n```tsx\nconst extra = 1;\n```']) {
    assert.equal(inspectReply(markdown(code, notes), profile).contractSatisfied, false);
  }
  assert.equal(inspectReply(markdown(code, '1. 첫째\n3. 셋째\n4. 넷째'), { ...profile, explanation: 'steps' }).contractSatisfied, false);
  assert.equal(inspectReply(markdown(code, '- `Counter`를 사용합니다.'), profile).contractSatisfied, true);
  assert.equal(inspectReply(markdown(code, '- 설명'), { ...profile, explanation: 'none' }).contractSatisfied, false);
});

test('가짜 export 문자열과 함수가 아닌 export는 컴포넌트로 세지 않는다', () => {
  for (const source of ['// export function Counter() {}', 'export const Counter = "fake";', 'const text = "export function Counter() {}";']) {
    assert.equal(inspectReply(markdown(source, '- 설명'), profile).checks.exportedComponent, false);
  }
});

test('TSX 문법 오류와 명시적 any, 외부 import를 검출한다', () => {
  assert.equal(inspectReply(markdown('export function Counter( {', '- 설명'), profile).checks.syntax, false);
  assert.equal(inspectReply(markdown('export function Counter(props: any) { return <button />; }', '- 설명'), profile).checks.noExplicitAny, false);
  for (const prefix of ['import x from "unknown-package";', 'const x = require("fs");', 'import("other");']) {
    assert.equal(inspectReply(markdown(`${prefix}\n${code}`, '- 설명'), profile).checks.imports, false);
  }
});

test('JSON의 추가 파일, 추가 키, 빈 설명 항목은 거절한다', () => {
  const jsonProfile = { ...profile, delivery: 'json' };
  for (const body of [
    { files: { 'Component.tsx': code, 'other.tsx': code }, explanation: ['설명'] },
    { files: { 'Component.tsx': code }, explanation: ['설명'], extra: true },
    { files: { 'Component.tsx': code }, explanation: [''] },
  ]) assert.equal(inspectReply(JSON.stringify(body), jsonProfile).contractSatisfied, false);
});

test('기능이 없는 버튼도 형식만 통과할 수 있으며 기능 성공으로 바꾸지 않는다', () => {
  const report = inspectReply(markdown(code, '- 클릭 동작은 구현하지 않았습니다.'), profile);
  assert.equal(report.contractSatisfied, true);
  assert.equal(report.functionalCorrectness, 'not_run');
  assert.equal(report.jointSuccess, null);
});

test('지원하지 않는 설정과 지나치게 긴 입력을 거절한다', () => {
  assert.throws(() => buildPrompt({ explanation: 'anything', delivery: 'markdown' }));
  assert.equal(inspectReply('x'.repeat(100_001), profile).contractSatisfied, false);
});
