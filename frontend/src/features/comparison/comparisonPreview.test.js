import test from 'node:test';
import assert from 'node:assert/strict';
import { mount } from '../../../test-support/appHarness.js';

const component = 'export function Counter() { return <button>Count</button>; }';
const plainStyle = 'export const panelStyle = { padding: 16 };';
const tokenStyle = 'export const panelStyle = { padding: tokens.space.medium };';
const answer = style => [
  '`Counter.tsx`', '```tsx', component, '```',
  '`styles.ts`', '```ts', style, '```',
].join('\n');

for (const scenario of [
  { name: '스타일 비교는 서로 다른 스타일 파일을 카드에 표시한다', axis: 'style_management',
    values: ['direct', 'theme'], texts: [answer(plainStyle), answer(tokenStyle)], expected: [plainStyle, tokenStyle] },
  { name: '코드 구성 비교는 첫 컴포넌트 미리 보기를 유지한다', axis: 'code_structure',
    values: ['compact', 'separated'], texts: [answer(plainStyle), answer(tokenStyle)], expected: [component, component] },
  { name: '스타일 파일 제목이 없어도 코드와 일반 텍스트를 표시한다', axis: 'style_management',
    values: ['direct', 'theme'], texts: ['```ts\nconst size = 16;\n```', 'Plain response'], expected: ['const size = 16;', 'Plain response'] },
]) {
  test(scenario.name, async () => {
    const ui = await mount('https://example.test/?team=team-invited', 'coding', async path => {
      if (path !== '/api/sessions') return null;
      return { ok: true, status: 201, json: async () => ({ session: {
        session_id: 'preview', total_rounds: 3, answered: 0, done: false, demo_mode: true,
        source_text: 'Preview regression check', pair: { pair_id: 'styles',
          a: { text: scenario.texts[0], combo: { [scenario.axis]: scenario.values[0] } },
          b: { text: scenario.texts[1], combo: { [scenario.axis]: scenario.values[1] } },
        },
      } }) };
    });
    try {
      await ui.click('내 선호 고르기 시작');
      await ui.click('이 내용으로 시작');
      assert.deepEqual([...document.querySelectorAll('.comparison-option pre')].map(el => el.textContent), scenario.expected);
      await ui.click('코드 전체 보기');
      assert.equal(document.querySelector('.comparison-preview-dialog pre').textContent, scenario.texts[0]);
    } finally { await ui.close(); }
  });
}
