import test from 'node:test';
import assert from 'node:assert/strict';
import { mount } from '../../../test-support/appHarness.js';
import { CODING_CHOICES } from './codingOptions.js';

function codingServer({ loggedIn = true } = {}) {
  const state = { loggedIn, records: [], previews: [], exampleRequests: [], writes: 0, failPreview: false, failSave: false, failExamples: false };
  const response = (data, status = 200) => ({ ok: status < 400, status, json: async () => structuredClone(data) });
  const fetch = async (path, options) => {
    const body = options.body ? JSON.parse(options.body) : {};
    if (path === '/api/auth/me') return response({ user: state.loggedIn ? { id: 1, username: 'alice' } : null });
    if (path === '/api/auth/login') { state.loggedIn = true; return response({ user: { id: 1, username: 'alice' } }); }
    if (path === '/api/coding-instructions/examples') {
      state.exampleRequests.push(body.profile);
      if (state.failExamples) return response({ error: '코드 예시를 불러오지 못했어요.' }, 400);
      const fastapi = body.profile.language === 'Python' && body.profile.framework === 'FastAPI';
      const spring = body.profile.language === 'Java' && body.profile.framework === 'Spring Boot';
      const source = fastapi || spring ? { id: fastapi ? 'fastapi-orders-v1' : 'spring-boot-orders-v1', kind: 'framework',
        label: `${body.profile.language} · ${body.profile.framework} · 주문 합계 API` } : null;
      const mainName = fastapi ? 'main.py' : 'OrderController.java';
      const secondName = fastapi ? 'orders.py' : 'OrderService.java';
      return response({ examples: { version: source ? 2 : 1, source, language: body.profile.language, framework: body.profile.framework,
        task: '배송비를 더하는 주문 합계', notice: '준비된 언어 기본 문법 예시',
        pairs: Object.entries(CODING_CHOICES).map(([axis, field]) => ({ axis, label: field.label, question: field.label,
          before: axis === 'output' ? '기존 코드 배송비 3000' : null,
          options: Object.entries(field.options).map(([value, label]) => ({ value, label,
            code: `${body.profile.language} ${axis} ${value}`, explanation: label,
            ...(source ? { files: [{ name: mainName, code: fastapi ? '@app.get("/orders/total")' : '@RestController' },
              ...(value === 'modular' ? [{ name: secondName, code: fastapi ? 'router = APIRouter()' : '@Service' }] : [])] } : {}) })) })) } });
    }
    if (path === '/api/coding-instructions/preview') {
      state.previews.push(body.profile);
      if (state.failPreview) return response({ error: '지침을 만들지 못했어요.' }, 400);
      return response({ draft: { profile: body.profile, prompt: `개발 언어: ${body.profile.language}\n프레임워크: ${body.profile.framework}\n선호: ${JSON.stringify(body.profile.preferences)}\n${body.profile.extra}` } });
    }
    if (path === '/api/preferences' && options.method === 'POST') {
      if (state.failSave) return response({ error: '저장하지 못했어요.' }, 409);
      state.writes += 1;
      const item = { id: `p${state.writes}`, title: body.title, domain_key: body.domainKey, prompt: body.prompt, note: body.note,
        coding_profile: body.codingProfile, coding_profile_matches: true, revision: 1, created_at: '2026-11-03T01:00:00Z', updated_at: '2026-11-03T01:00:00Z' };
      state.records.unshift(item);
      return response({ preference: item }, 201);
    }
    if (path === '/api/preferences') return response({ preferences: state.records });
    const [, , , id, action] = path.split('/');
    const item = state.records.find((r) => r.id === id);
    if (item && !action) return response({ preference: item });
    if (item && action === 'update') {
      Object.assign(item, { prompt: body.prompt, title: body.title, note: body.note, revision: item.revision + 1, coding_profile_matches: false });
      return response({ preference: item });
    }
    return null;
  };
  return { state, fetch };
}

async function openCoding(ui) {
  await ui.act(async () => document.querySelector('[aria-label="코딩 도움 선택"]').click());
  await ui.act(async () => document.querySelector('.selection-button').click());
}
async function press(ui, label) {
  const button = [...document.querySelectorAll('button')].find(item => item.getAttribute('aria-label') === label);
  assert.ok(button, label); assert.equal(button.disabled, false, label);
  await ui.act(async () => button.click());
}
function button(label) { return [...document.querySelectorAll('button')].find(item => item.textContent.trim() === label); }
async function environment(ui, language = 'Python', framework = 'FastAPI') {
  if (!document.querySelector(`[aria-label="${language} 선택"]`)) await ui.click('다른 언어도 보기 · 전체 14개');
  await press(ui, `${language} 선택`);
  await press(ui, framework ? `${framework} 선택` : '프레임워크 없이 선택');
}
const PICKS = { explanation: 'steps', comments: 'detailed', structure: 'modular', output: 'changes' };
async function pickCards(ui, picks = PICKS) {
  for (const [key, value] of Object.entries(picks)) await press(ui, `${CODING_CHOICES[key].label}: ${CODING_CHOICES[key].options[value]}`);
}
async function directReview(ui) {
  await openCoding(ui); await environment(ui); await ui.click('설정 카드로 직접 고를게요');
  await pickCards(ui); await ui.click('내 선택 확인하기 →');
}
async function selectExample(ui, index) {
  await ui.act(async () => document.querySelectorAll('.coding-option-select')[index].click());
}
async function nextExample(ui) {
  await ui.click(button('4가지 선택 확인하기 →') ? '4가지 선택 확인하기 →' : '이 선택으로 다음 →');
}

test('처음에는 환경·선호가 미선택이며 네 항목을 직접 골라야 프롬프트를 만든다', async () => {
  const api = codingServer(); const ui = await mount('https://example.test/', 'coding', api.fetch);
  try {
    await openCoding(ui);
    assert.equal(document.querySelectorAll('.coding-language-buttons [aria-pressed="true"]').length, 0);
    assert.ok(button('코드 예시 비교 시작하기 →').disabled);
    assert.equal(button('내 선택으로 프롬프트 만들기'), undefined);
    await press(ui, 'Python 선택'); assert.ok(button('코드 예시 비교 시작하기 →').disabled);
    await press(ui, 'FastAPI 선택'); await ui.click('설정 카드로 직접 고를게요');
    assert.equal(document.querySelectorAll('.coding-preference-buttons [aria-pressed="true"]').length, 0);
    assert.ok(button('내 선택 확인하기 →').disabled);
    await pickCards(ui, { explanation: 'steps', comments: 'detailed', structure: 'modular' });
    assert.ok(button('내 선택 확인하기 →').disabled);
    assert.equal(api.state.previews.length, 0);
    await pickCards(ui, { output: 'changes' }); await ui.click('내 선택 확인하기 →');
    assert.ok(document.querySelector('.coding-next-bar').textContent.includes('답변 방식 4가지 선택 완료'));
    await ui.click('내 선택으로 프롬프트 만들기');
    assert.deepEqual(api.state.previews[0].preferences, PICKS);
    assert.equal(api.state.previews[0].comparison, undefined);
    assert.equal(document.querySelector('#coding-instructions-prompt').closest('details'), null);
    assert.ok(document.querySelector('[aria-labelledby="coding-summary-title"]').textContent.includes('내가 고른 답변 방식'));
    assert.ok(document.querySelector('[aria-labelledby="coding-actual-prompt-title"]').textContent.includes('AI에 붙여넣을 프롬프트'));
    assert.ok(document.querySelector('#coding-instructions-prompt').value.includes('FastAPI'));
    assert.equal(document.querySelectorAll('.coding-choice-answer').length, 4);
    assert.equal(ui.state.sessions, 0);
  } finally { await ui.close(); }
});

test('직접 선택 생성·복사·저장 실패 보존 → 재사용·다른 환경에서 새 항목, 원본 유지', async () => {
  const api = codingServer(); const ui = await mount('https://example.test/', 'coding', api.fetch);
  try {
    await directReview(ui); await ui.fill('#coding-extra', '설명은 한국어로');
    api.state.failPreview = true; await ui.click('내 선택으로 프롬프트 만들기');
    assert.ok(document.querySelector('[role="alert"]'));
    assert.equal(document.querySelectorAll('.coding-preference-buttons [aria-pressed="true"]').length, 4);
    api.state.failPreview = false; await ui.click('내 선택으로 프롬프트 만들기');
    await ui.click('프롬프트 복사'); assert.ok(ui.state.copied.includes('Python'));
    await ui.fill('#save-preference-title', '내 Python 방식'); api.state.failSave = true;
    await ui.click('내 선호 보관함에 저장');
    assert.equal(document.querySelector('#save-preference-title').value, '내 Python 방식');
    assert.ok(document.querySelector('#coding-instructions-prompt').value.includes('FastAPI'));
    api.state.failSave = false; await ui.click('내 선호 보관함에 저장');
    const original = structuredClone(api.state.records[0]);
    await ui.click('저장한 지침 열기'); await ui.click('예시 자료 넣어보기');
    await ui.click('지침 + 새 작업 복사'); assert.ok(ui.state.copied.includes(original.prompt));
    ui.dom.window.confirm = () => false; await ui.click('이 설정으로 새 지침 만들기');
    assert.ok(document.querySelector('#preference-task'));
    ui.dom.window.confirm = () => true; await ui.click('이 설정으로 새 지침 만들기');
    assert.equal(document.querySelector('[aria-label="FastAPI 선택"]').getAttribute('aria-pressed'), 'true');
    await press(ui, 'FastAPI 선택');
    await ui.click('저장한 선택으로 계속하기');
    assert.equal(document.querySelectorAll('.coding-preference-buttons [aria-pressed="true"]').length, 4);
    await ui.click('개발 환경 다시 고르기'); await environment(ui, 'Java', 'Spring Boot');
    await ui.click('설정 카드로 직접 고를게요');
    assert.equal(document.querySelectorAll('.coding-preference-buttons [aria-pressed="true"]').length, 0);
    await pickCards(ui); await ui.click('내 선택 확인하기 →'); await ui.click('내 선택으로 프롬프트 만들기');
    await ui.click('내 선호 보관함에 저장');
    assert.equal(api.state.records.length, 2); assert.deepEqual(api.state.records[1], original);
    assert.equal(api.state.records[0].coding_profile.language, 'Java');
  } finally { await ui.close(); }
});

test('예시 선택 확인·이전 선택 수정과 보류 후 직접 선택, 기본값 없이 저장', async () => {
  const api = codingServer(); const ui = await mount('https://example.test/', 'coding', api.fetch);
  try {
    await openCoding(ui); await environment(ui); await ui.click('코드 예시 비교 시작하기 →');
    assert.ok(button('이 선택으로 다음 →').disabled);
    await selectExample(ui, 1);
    assert.ok(document.querySelector('.coding-picked-answer').textContent.includes('과정과 이유'));
    assert.ok(document.querySelector('.coding-example-comparison h3').textContent.includes('설명 방식'));
    await nextExample(ui);
    await ui.click('예시는 보류할게요'); await nextExample(ui);
    await selectExample(ui, 1); await nextExample(ui);
    await ui.click('이전 항목'); await selectExample(ui, 0); await nextExample(ui);
    await selectExample(ui, 1); await nextExample(ui);
    assert.ok(document.querySelector('.coding-selection-status').textContent.includes('남은 1개'));
    assert.ok(button('내 선택으로 프롬프트 만들기').disabled);
    assert.equal(api.state.previews.length, 0);
    await pickCards(ui, { comments: 'detailed' });
    await ui.click('내 선택으로 프롬프트 만들기');
    const expected = { version: 2, choices: { explanation: 'steps', comments: null, structure: 'compact', output: 'changes' },
      example: { id: 'fastapi-orders-v1', kind: 'framework', label: 'Python · FastAPI · 주문 합계 API' } };
    assert.deepEqual(api.state.previews[0].comparison, expected);
    assert.equal(api.state.previews[0].preferences.comments, 'detailed');
    await ui.click('내 선호 보관함에 저장'); await ui.click('저장한 지침 열기');
    assert.ok(document.querySelector('.saved-coding-profile').textContent.includes('직접 설정 · 비교 보류'));
    assert.ok(document.querySelector('.saved-coding-profile').textContent.includes('FastAPI · 주문 합계 API'));
  } finally { await ui.close(); }
});

test('예시 조회 실패·비교 취소는 임시 선택을 반영하지 않으며 파일 버튼으로 Spring 예시를 연다', async () => {
  const api = codingServer(); const ui = await mount('https://example.test/', 'coding', api.fetch);
  try {
    await openCoding(ui); await environment(ui, 'Java', 'Spring Boot');
    api.state.failExamples = true; await ui.click('코드 예시 비교 시작하기 →');
    assert.ok(document.querySelector('[role="alert"]')); assert.equal(api.state.previews.length, 0);
    api.state.failExamples = false; await ui.click('코드 예시 비교 시작하기 →');
    await selectExample(ui, 0); await ui.click('비교 취소');
    await ui.click('설정 카드로 직접 고를게요');
    assert.equal(document.querySelectorAll('.coding-preference-buttons [aria-pressed="true"]').length, 0);
    await ui.act(async () => document.querySelector('.coding-stepper button').click());
    await ui.click('코드 예시 비교 시작하기 →');
    await selectExample(ui, 1); await nextExample(ui); await selectExample(ui, 0); await nextExample(ui);
    await ui.click('OrderService.java');
    assert.ok(document.querySelectorAll('.coding-code-preview pre')[1].textContent.includes('@Service'));
    await selectExample(ui, 1); await nextExample(ui); await selectExample(ui, 1); await nextExample(ui);
    await ui.click('내 선택으로 프롬프트 만들기'); await ui.click('내 선호 보관함에 저장');
    assert.equal(api.state.records[0].coding_profile.comparison.example.id, 'spring-boot-orders-v1');
  } finally { await ui.close(); }
});

test('직접 선택 화면에서 코드 비교로 전환하고 실패·취소하면 기존 설정으로 돌아온다', async () => {
  const api = codingServer(); const ui = await mount('https://example.test/', 'coding', api.fetch);
  try {
    await openCoding(ui); await environment(ui); await ui.click('설정 카드로 직접 고를게요');
    await pickCards(ui, { explanation:'steps', comments:'detailed' });
    assert.equal(document.querySelector('[aria-label="설정만 빠르게 고르기"]').getAttribute('aria-pressed'),'true');
    api.state.failExamples = true; await press(ui,'코드 예시로 고르기');
    assert.ok(document.querySelector('[role="alert"]'));
    assert.equal(document.querySelectorAll('.coding-preference-buttons [aria-pressed="true"]').length,2);
    api.state.failExamples = false; await press(ui,'코드 예시로 고르기');
    assert.equal(document.querySelector('[aria-label="코드 예시로 고르기"]').getAttribute('aria-pressed'),'true');
    assert.equal(document.querySelectorAll('.coding-code-preview pre').length,2);
    assert.ok(document.querySelector('.coding-example-scope').textContent.includes('FastAPI 전용 코드 예시'));
    assert.equal(document.querySelector('.coding-example-scope').closest('details'),null);
    assert.equal(document.querySelectorAll('.coding-option-select[aria-pressed="true"]').length,0,'direct settings are not presented as confirmed code choices');
    await selectExample(ui,0); await ui.click('비교 취소');
    assert.equal(document.querySelector('[aria-label="설정만 빠르게 고르기"]').getAttribute('aria-pressed'),'true');
    assert.equal(document.querySelector('[aria-label="설명 방식: 과정과 이유를 단계별로"]').getAttribute('aria-pressed'),'true');
    assert.equal(document.querySelectorAll('.coding-preference-buttons [aria-pressed="true"]').length,2);
    assert.equal(api.state.previews.length,0);
    await pickCards(ui, { structure:'modular', output:'changes' });
    await ui.click('내 선택 확인하기 →'); await ui.click('내 선택으로 프롬프트 만들기');
    assert.deepEqual(api.state.previews[0].preferences,PICKS);
    assert.equal(api.state.previews[0].comparison,undefined);
  } finally { await ui.close(); }
});

test('결과에서 선택을 다시 확인하며 코드 비교를 취소하면 생성문을 유지하고 완료하면 새 선택을 반영한다', async () => {
  const api = codingServer(); const ui = await mount('https://example.test/', 'coding', api.fetch);
  try {
    await directReview(ui); await ui.click('내 선택으로 프롬프트 만들기');
    const original = document.querySelector('#coding-instructions-prompt').value;
    await ui.click('선택 다시 바꾸기'); await ui.click('코드 예시를 보며 다시 고르기');
    await selectExample(ui,0); await ui.click('비교 취소');
    assert.ok(button('내 선택으로 프롬프트 만들기'));
    await ui.act(async () => [...document.querySelectorAll('.coding-stepper button')].find(item => item.textContent.endsWith('내 프롬프트')).click());
    assert.equal(document.querySelector('#coding-instructions-prompt').value,original);
    assert.equal(api.state.previews.length,1);
    await ui.click('선택 다시 바꾸기'); await ui.click('코드 예시를 보며 다시 고르기');
    for (let at=0;at<4;at+=1) { await selectExample(ui,0); await nextExample(ui); }
    await ui.click('내 선택으로 프롬프트 만들기');
    assert.equal(api.state.previews.length,2);
    assert.equal(api.state.previews[1].comparison.version,2);
    assert.equal(api.state.previews[1].comparison.choices.explanation,'brief');
    assert.ok(document.querySelector('.coding-summary-panel').textContent.includes('예시에서 골랐어요'));
    assert.equal(api.state.writes,0);
  } finally { await ui.close(); }
});

test('언어 기본 예시 범위는 펼치지 않아도 보이며 미지원 직접 입력은 코드 비교를 켜지 않는다', async () => {
  const api = codingServer(); const ui = await mount('https://example.test/', 'coding', api.fetch);
  try {
    await openCoding(ui); await environment(ui,'TypeScript','NestJS'); await ui.click('설정 카드로 직접 고를게요');
    await press(ui,'코드 예시로 고르기');
    assert.ok(document.querySelector('.coding-example-scope').textContent.includes('TypeScript 기본 문법 코드 예시'));
    assert.equal(document.querySelector('.coding-example-scope').closest('details'),null);
    await ui.click('비교 취소');
    await ui.act(async () => document.querySelector('.coding-stepper button').click()); await press(ui,'언어 직접 입력'); await ui.fill('#coding-language-custom','Elixir');
    await press(ui,'프레임워크 없이 선택'); await ui.click('설정 카드로 선택하기 →');
    assert.ok(document.querySelector('[aria-label="코드 예시로 고르기"]').disabled);
    assert.ok(document.querySelector('.coding-selection-method-hint').textContent.includes('직접 입력한 언어'));
    assert.equal(api.state.exampleRequests.length,1);
  } finally { await ui.close(); }
});

test('직접 입력한 언어·프레임워크의 빈 값과 명시적 카드 선택을 확인한다', async () => {
  const api = codingServer(); const ui = await mount('https://example.test/', 'coding', api.fetch);
  try {
    await openCoding(ui); await press(ui, '언어 직접 입력');
    assert.ok(button('코드 예시 비교 시작하기 →').disabled);
    await ui.fill('#coding-language-custom', 'Elixir'); await ui.click('프레임워크 직접 입력');
    assert.ok(button('설정 카드로 선택하기 →').disabled);
    await ui.fill('#coding-framework-custom', 'Phoenix 1.x'); await ui.click('설정 카드로 선택하기 →');
    await pickCards(ui); await ui.click('내 선택 확인하기 →'); await ui.click('내 선택으로 프롬프트 만들기');
    assert.equal(api.state.exampleRequests.length, 0);
    assert.equal(api.state.previews[0].language, 'Elixir'); assert.equal(api.state.previews[0].framework, 'Phoenix 1.x');
    assert.equal(api.state.previews[0].comparison, undefined);
  } finally { await ui.close(); }
});

test('로그인 중 선택 결과·생성 지침·저장 이름이 유지되고 명시적으로 저장한다', async () => {
  const api = codingServer({ loggedIn: false }); const ui = await mount('https://example.test/', 'coding', api.fetch);
  try {
    await directReview(ui); await ui.click('내 선택으로 프롬프트 만들기');
    const prompt = document.querySelector('#coding-instructions-prompt').value;
    await ui.fill('#save-preference-title', '로그인 전 이름'); await ui.click('로그인하고 보관함에 저장');
    await ui.fill('#auth-username', 'alice'); await ui.fill('#auth-password', 'alice-password');
    await ui.act(async () => document.querySelector('.auth-form').dispatchEvent(new ui.dom.window.Event('submit', { bubbles: true, cancelable: true })));
    assert.equal(document.querySelector('#coding-instructions-prompt').value, prompt);
    assert.equal(document.querySelector('#save-preference-title').value, '로그인 전 이름');
    assert.equal(api.state.writes, 0);
    await ui.click('내 선호 보관함에 저장'); await ui.click('저장한 지침 열기');
    await ui.click('지침 수정'); await ui.fill('#preference-prompt', '직접 고친 내용'); await ui.click('변경 내용 저장');
    assert.ok(document.querySelector('.saved-coding-profile').textContent.includes('처음 저장한 설정'));
  } finally { await ui.close(); }
});

test('과거 기본 문법 비교 저장본은 그대로 재사용하고 결과를 직접 고치면 해당 항목만 직접 선택으로 바뀐다', async () => {
  const api = codingServer();
  const profile = { language: 'Python', framework: 'FastAPI', extra: '', preferences: { ...PICKS },
    comparison: { version: 1, choices: { ...PICKS } } };
  api.state.records.push({ id: 'old', title: '이전 기본 문법', domain_key: 'coding', prompt: '이전 지침', note: '', revision: 1,
    coding_profile: profile, coding_profile_matches: true, created_at: '2026-11-03T01:00:00Z', updated_at: '2026-11-03T01:00:00Z' });
  const ui = await mount('https://example.test/', 'coding', api.fetch);
  try {
    await ui.click('내 선호 보관함'); await ui.click('새 작업에 사용');
    assert.ok(document.querySelector('.saved-coding-profile').textContent.includes('언어 기본 문법 · 프레임워크 전용 비교 아님'));
    ui.dom.window.confirm = () => true; await ui.click('이 설정으로 새 지침 만들기');
    await ui.click('저장한 선택으로 계속하기'); await ui.click('내 선택으로 프롬프트 만들기');
    await ui.click('선택 다시 바꾸기'); await pickCards(ui, { structure: 'compact' });
    await ui.click('내 선택으로 프롬프트 만들기');
    assert.equal(api.state.previews.at(-1).comparison.choices.structure, null);
    assert.equal(api.state.previews.at(-1).comparison.choices.explanation, 'steps');
    assert.equal(api.state.records[0].coding_profile.comparison.choices.structure, 'modular');
    assert.equal(api.state.records[0].prompt, '이전 지침');
  } finally { await ui.close(); }
});

test('기존 React 비교와 선택 결과를 유지하며 새 환경 카드 화면과 오간다', async () => {
  const api = codingServer(); const ui = await mount('https://example.test/', 'coding', api.fetch);
  try {
    await openCoding(ui);
    await ui.act(async () => document.querySelector('.coding-legacy-entry summary').click());
    await ui.click('React 예시 비교로 취향 찾기'); assert.ok(document.querySelector('#coding-task'));
    await ui.click('다른 언어·프레임워크로 지침 만들기'); assert.ok(document.querySelector('.coding-language-buttons'));
    await ui.act(async () => document.querySelector('.coding-legacy-entry summary').click());
    await ui.click('React 예시 비교로 취향 찾기'); await ui.click('이 내용으로 시작');
    await ui.act(async () => document.querySelector('[aria-label^="예시 A 선택"]').click());
    assert.equal(ui.state.sessions, 1); assert.ok(document.body.textContent.includes('나만의 코딩 프롬프트가 완성됐어요'));
  } finally { await ui.close(); }
});

test('선택 요약과 실제 프롬프트를 펼치지 않고 보며, 새 작업과 함께 복사해도 지침만 저장한다', async () => {
  const api = codingServer(); const ui = await mount('https://example.test/', 'coding', api.fetch);
  try {
    await directReview(ui); await ui.click('내 선택으로 프롬프트 만들기');
    const prompt = document.querySelector('#coding-instructions-prompt').value;
    const task = '회원가입 API를 만들어줘. 중복 이메일을 거절해줘.';
    assert.equal(document.querySelector('#coding-instructions-prompt').closest('details'), null);
    assert.equal(document.querySelectorAll('.coding-summary-panel .coding-choice-answer').length, 4);
    assert.ok(button('내 답변 방식 + 이번 작업 복사').disabled);
    assert.ok(document.querySelector('.coding-how-to-use').textContent.includes('AI 대화창에 붙여넣기'));
    await ui.fill('#coding-new-task', task); await ui.click('내 답변 방식 + 이번 작업 복사');
    assert.equal(ui.state.copied, `${prompt}\n\n## 이번 작업 요청\n${task}`);
    assert.equal(api.state.previews.length, 1);
    await ui.click('프롬프트 복사'); assert.equal(ui.state.copied, prompt);
    await ui.click('내 선호 보관함에 저장');
    const original = structuredClone(api.state.records[0]);
    assert.equal(original.prompt, prompt);
    assert.equal(JSON.stringify(original).includes(task), false);
    assert.equal(document.querySelector('#coding-new-task').value, task);
    await ui.click('내 답변 방식 + 이번 작업 복사');
    await ui.click('선택 다시 바꾸기'); await pickCards(ui, { structure: 'compact' });
    await ui.click('내 선택으로 프롬프트 만들기');
    assert.ok(button('내 답변 방식 + 이번 작업 복사'));
    assert.equal(document.querySelector('#coding-new-task').value, task);
    assert.deepEqual(api.state.records[0], original);
    await ui.fill('#coding-new-task', '   ');
    assert.ok(button('내 답변 방식 + 이번 작업 복사').disabled);
  } finally { await ui.close(); }
});
