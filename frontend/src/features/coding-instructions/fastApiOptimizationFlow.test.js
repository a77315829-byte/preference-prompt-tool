import test from 'node:test';
import assert from 'node:assert/strict';
import { mount } from '../../../test-support/appHarness.js';
import { CODING_CHOICES } from './codingOptions.js';

const BASE = '/api/coding-instructions/optimizations';
const ORIGINAL = 'Python · FastAPI 원본 지침. 선택한 작성 방식을 유지하세요.';
const GUIDANCE = '입력 제약과 계산 결과를 확인하세요.';
const CANDIDATE = `${ORIGINAL}\n\nGEPA 보충 안내\n${GUIDANCE}`;
const PROFILE = { language: 'Python', framework: 'FastAPI', preferences: { explanation: 'brief', comments: 'essential', structure: 'compact', output: 'complete' }, extra: '' };
const TASKS = [{ id: 'one', label: '대여 견적', request: '대여 API를 만드세요.', response: '기존 코드' }, { id: 'two', label: '인쇄 요금', request: '인쇄 API를 만드세요.', response: '인쇄 기존 코드' }];
const REPORT = { validation_tasks: 2, validation_before: .7, validation_after: .9, holdout_tasks: 2,
  holdout_before: { score: .65, contracts_passed: 1, tasks: TASKS }, holdout_after: { score: .85, contracts_passed: 2, tasks: TASKS.map(t => ({ ...t, response: `${t.response} 개선` })) },
  limitation: '실제 서버 실행 검증은 아닙니다.', preference_checks: '형식 대리 검사입니다.', model_calls: 12 };

function backend(profile = PROFILE, prompt = ORIGINAL) {
  const candidate = `${prompt}\n\nGEPA 보충 안내\n${GUIDANCE}`;
  const original = { id: 'original', title: `원래 ${profile.framework} 지침`, domain_key: 'coding', prompt, coding_profile: profile,
    coding_profile_matches: true, revision: 1, note: '', created_at: '2026-11-04', updated_at: '2026-11-04' };
  const state = { records: [original], calls: [], enabled: true, environments: null, changed: true, report: REPORT, failStart: false, failSave: false, running: false, defer: null, polls: 0 };
  const response = (value, status = 200) => ({ ok: status < 400, status, json: async () => structuredClone(value) });
  const result = () => ({ profile, original_prompt: prompt, improved_prompt: state.changed ? candidate : prompt,
    guidance: state.changed ? GUIDANCE : '', changed: state.changed, report: { ...state.report,
      ...(!state.changed ? { validation_after: state.report.validation_before, holdout_after: state.report.holdout_before } : {}),
      ...(profile.language === 'Java' ? { limitation: 'Java 컴파일·Spring 서버 실행 검증은 아닙니다.' } : {}) } });
  const job = () => ({ id: 'j1', status: state.running ? 'running' : 'done', stage: '별도 과제를 확인하는 중', model_calls: 7, result: state.running ? null : result() });
  const fetch = async (path, options) => {
    const body = options.body ? JSON.parse(options.body) : {};
    state.calls.push({ path, body, method: options.method });
    if (path === '/api/auth/me') return response({ user: { id: 1, username: 'alice' } });
    if (path === '/api/coding-instructions/preview') return response({ draft: { profile: body.profile, prompt } });
    if (path === BASE && !options.method) return response({ enabled: state.enabled, environments: state.environments, call_limit: 32, reason: '실제 호출 설정을 준비해 주세요.' });
    if (path === BASE && options.method === 'POST') {
      if (state.failStart) return response({ error: '오늘 개선 횟수를 모두 썼어요.' }, 400);
      if (state.defer) await state.defer;
      return response({ job: job() }, 202);
    }
    if (path === `${BASE}/j1`) { state.polls += 1; return response({ job: job() }); }
    if (path === `${BASE}/j1/save`) {
      if (state.failSave) return response({ error: '저장하지 못했어요.' }, 400);
      assert.ok(Object.keys(body).every(key => ['title', 'humanReview'].includes(key)));
      const item = { ...original, id: 'new', title: body.title, prompt: candidate,
        coding_optimization: { method: 'gepa', original_prompt: prompt, guidance: GUIDANCE, report: result().report, ...(body.humanReview ? { human_review: body.humanReview } : {}) } };
      state.records.unshift(item); return response({ preference: item }, 201);
    }
    if (path === '/api/preferences') return response({ preferences: state.records });
    if (path === '/api/coding-instructions/review') return response({ inspection: { version: 'coding-answer-review-v2', preferences: { explanation: true, comments: null, structure: null, output: null }, observations: { comments: '// 입력 제한의 이유', structure: '역할과 규모의 적절함은 직접 확인' }, guidance: {} } });
    const item = state.records.find(record => path === `/api/preferences/${record.id}`);
    if (item) return response({ preference: item });
    return null;
  };
  return { state, fetch };
}

async function openResult(ui, language = 'Python', framework = 'FastAPI', preferences = PROFILE.preferences) {
  await ui.act(async () => document.querySelector('[aria-label="코딩 도움 선택"]').click());
  await ui.act(async () => document.querySelector('.selection-button').click());
  await ui.act(async () => {
    const target = [...document.querySelectorAll('button[aria-label]')].find(button => button.getAttribute('aria-label') === `${language} 선택`);
    assert.ok(target, `Language missing: ${language}; available: ${[...document.querySelectorAll('button[aria-label]')].map(button => button.getAttribute('aria-label')).join(', ')}`);
    target.click();
  });
  await ui.act(async () => document.querySelector(`[aria-label="${framework} 선택"]`).click());
  await ui.click('설정 카드로 직접 고를게요');
  for (const [axis, field] of Object.entries(CODING_CHOICES)) {
    await ui.act(async () => document.querySelector(`[aria-label="${field.label}: ${field.options[preferences[axis]]}"]`).click());
  }
  await ui.click('내 선택 확인하기 →'); await ui.click('내 선택으로 프롬프트 만들기');
}
const button = text => [...document.querySelectorAll('button')].find(b => b.textContent.trim() === text);

test('GEPA 전후·별도 과제 비교 → 명시적 채택 → 새 항목 저장·다시 열기, 원본 유지', async () => {
  const api = backend(); const ui = await mount('https://example.test/', 'coding', api.fetch);
  const before = structuredClone(api.state.records[0]);
  try {
    await openResult(ui);
    assert.equal(api.state.calls.filter(c => c.path === BASE && c.method).length, 0, 'no automatic paid requests');
    await ui.fill('#coding-new-task', 'PRIVATE CURRENT WORK');
    await ui.click('실제 AI로 GEPA 개선 시작');
    const start = api.state.calls.find(c => c.path === BASE && c.method);
    assert.equal(start.body.originalPrompt, ORIGINAL);
    assert.ok(!JSON.stringify(start.body).includes('PRIVATE CURRENT WORK'));
    assert.equal(document.querySelector('#fastapi-gepa-original').value, ORIGINAL);
    assert.equal(document.querySelector('#fastapi-gepa-candidate').value, CANDIDATE);
    assert.equal(document.querySelector('#coding-instructions-prompt').value, ORIGINAL);
    assert.equal(button('개선 후보를 새 항목으로 저장'), undefined);
    await ui.click('기존 프롬프트 유지'); assert.equal(api.state.records.length, 1);
    await ui.act(async () => document.querySelector('.fastapi-gepa-examples summary').click());
    assert.equal(document.querySelector('#fastapi-gepa-answer-after').value, '기존 코드 개선');
    await ui.click('인쇄 요금'); assert.equal(document.querySelector('#fastapi-gepa-answer-after').value, '인쇄 기존 코드 개선');
    await ui.click('개선 후보를 새로 보관할게요'); await ui.fill('#fastapi-gepa-save-title', '검토한 새 FastAPI 지침');
    api.state.failSave = true; await ui.click('개선 후보를 새 항목으로 저장');
    assert.equal(document.querySelector('#fastapi-gepa-save-title').value, '검토한 새 FastAPI 지침');
    api.state.failSave = false; await ui.click('개선 후보를 새 항목으로 저장');
    assert.equal(api.state.records.length, 2); assert.deepEqual(api.state.records[1], before);
    await ui.click('저장한 개선 후보 열기');
    assert.ok(document.querySelector('.saved-gepa-origin').textContent.includes('GEPA로 다듬어 새로 보관한 지침'));
    assert.equal(document.querySelector('[aria-label="GEPA 개선 전 원본 프롬프트"]').value, ORIGINAL);
    assert.equal(api.state.calls.filter(c => c.path === BASE && c.method).length, 1);
  } finally { await ui.close(); }
});

test('실제 호출 꺼짐·시작 오류·개선 없음에서 원본과 저장본을 보존한다', async () => {
  const api = backend(); api.state.enabled = false;
  let ui = await mount('https://example.test/', 'coding', api.fetch);
  try { await openResult(ui); assert.ok(button('실제 AI로 GEPA 개선 시작').disabled); assert.equal(document.querySelector('#coding-instructions-prompt').value, ORIGINAL); }
  finally { await ui.close(); }
  api.state.enabled = true; api.state.failStart = true;
  ui = await mount('https://example.test/', 'coding', api.fetch);
  try {
    await openResult(ui); await ui.click('실제 AI로 GEPA 개선 시작');
    assert.ok(document.querySelector('.fastapi-optimization [role="alert"]').textContent.includes('횟수'));
    assert.equal(button('실제 AI로 GEPA 개선 시작').disabled, false);
    api.state.failStart = false; api.state.changed = false; await ui.click('실제 AI로 GEPA 개선 시작');
    assert.ok(document.querySelector('.fastapi-gepa-outcome').textContent.includes('추가 개선 확인 안 됨'));
    assert.ok(document.querySelector('.fastapi-gepa-outcome').textContent.includes('원본을 유지했어요'));
    assert.equal(button('개선 후보를 새로 보관할게요'), undefined);
    assert.equal(api.state.records.length, 1);
  } finally { await ui.close(); }
});

test('진행 중에는 선택·원본 저장을 잠그고, 폴링 완료 뒤 다시 사용할 수 있다', async () => {
  const api = backend(); api.state.running = true;
  const ui = await mount('https://example.test/', 'coding', api.fetch);
  try {
    await openResult(ui); await ui.click('실제 AI로 GEPA 개선 시작');
    assert.ok(button('선택 다시 바꾸기').disabled);
    assert.ok(button('내 선호 보관함에 저장').disabled);
    api.state.running = false;
    await ui.act(async () => new Promise(resolve => setTimeout(resolve, 1300)));
    assert.ok(api.state.polls > 0);
    assert.equal(button('선택 다시 바꾸기').disabled, false);
    assert.equal(document.querySelector('#fastapi-gepa-candidate').value, CANDIDATE);
  } finally { await ui.close(); }
});

test('화면을 떠난 뒤 도착한 개선 응답은 다른 화면에 반영하거나 저장하지 않는다', async () => {
  const api = backend(); let finish;
  api.state.defer = new Promise(resolve => { finish = resolve; });
  const ui = await mount('https://example.test/', 'coding', api.fetch);
  try {
    await openResult(ui); await ui.click('실제 AI로 GEPA 개선 시작');
    await ui.click('내 선호 보관함');
    await ui.act(async () => { finish(); });
    assert.equal(document.querySelector('.fastapi-optimization'), null);
    assert.equal(api.state.records.length, 1);
  } finally { await ui.close(); }
});

test('Java Spring Boot의 별도 활성화·전후 비교·채택·새 항목 저장과 재사용에서 원본 유지', async () => {
  const profile = { ...PROFILE, language: 'Java', framework: 'Spring Boot' };
  const original = 'Java · Spring Boot 원본 지침. 선택한 작성 방식은 유지하세요.';
  const api = backend(profile, original);
  api.state.enabled = false;
  api.state.environments = { fastapi: { enabled: false }, spring_boot: { enabled: true, reason: '' } };
  const ui = await mount('https://example.test/', 'coding', api.fetch);
  const snapshot = structuredClone(api.state.records[0]);
  try {
    await openResult(ui, 'Java', 'Spring Boot');
    assert.ok(document.querySelector('.fastapi-optimization .coding-kicker').textContent.includes('Spring Boot + GEPA'));
    assert.equal(button('실제 AI로 GEPA 개선 시작').disabled, false, 'Spring Boot uses its own capability');
    await ui.click('실제 AI로 GEPA 개선 시작');
    const sent = api.state.calls.find(call => call.path === BASE && call.method);
    assert.equal(sent.body.profile.language, 'Java'); assert.equal(sent.body.profile.framework, 'Spring Boot');
    assert.equal(document.querySelector('#fastapi-gepa-original').value, original);
    assert.equal(document.querySelector('#coding-instructions-prompt').value, original);
    assert.ok(document.querySelector('.fastapi-optimization').textContent.includes('Java 컴파일'));
    await ui.click('개선 후보를 새로 보관할게요');
    assert.ok(document.querySelector('#fastapi-gepa-save-title').value.startsWith('Spring Boot'));
    await ui.fill('#fastapi-gepa-save-title', '검토한 Spring Boot 새 후보'); await ui.click('개선 후보를 새 항목으로 저장');
    assert.deepEqual(api.state.records[1], snapshot); assert.equal(api.state.records.length, 2);
    await ui.click('저장한 개선 후보 열기');
    assert.ok(document.querySelector('.saved-coding-profile').textContent.includes('Java · Spring Boot'));
    assert.equal(document.querySelector('[aria-label="GEPA 개선 전 원본 프롬프트"]').value, original);
    await ui.fill('#preference-task', '상품 검색 API 구현');
    assert.ok(document.querySelector('#preference-request').value.includes(GUIDANCE));
    assert.ok(document.querySelector('#preference-request').value.includes('상품 검색 API 구현'));
  } finally { await ui.close(); }
});

test('FastAPI가 켜져 있어도 Spring Boot가 꺼졌거나 구형 서버이면 Spring 개선을 시작하지 않는다', async () => {
  for (const environments of [null, { fastapi: { enabled: true }, spring_boot: { enabled: false, reason: 'Spring Boot 설정이 꺼져 있어요.' } }]) {
    const api = backend({ ...PROFILE, language: 'Java', framework: 'Spring Boot' }, 'Spring 원본');
    api.state.environments = environments;
    const ui = await mount('https://example.test/', 'coding', api.fetch);
    try {
      await openResult(ui, 'Java', 'Spring Boot');
      assert.ok(button('실제 AI로 GEPA 개선 시작').disabled);
      assert.equal(api.state.calls.filter(call => call.path === BASE && call.method).length, 0);
      assert.equal(document.querySelector('#coding-instructions-prompt').value, 'Spring 원본');
    } finally { await ui.close(); }
  }
});

function springInspectionReport() {
  const tasks = TASKS.map(task => ({ ...task, score: .7375,
    checks: { code_structure: true, route: true, validation: true, calculation: true },
    preferences: { explanation: false, comments: false, structure: false, output: true },
    observations: { explanation: '코드 밖 설명 200자 · 인식된 줄 시작 번호/목록 없음', comments: 'Java 행·블록 주석 1개', structure: '클래스 1개', output: '새 구현 과제 · 클래스 선언 있음 · import 있음' },
  }));
  const batch = { score: .7375, contracts_passed: 2, tasks };
  return { ...REPORT, version: 'spring-boot-static-v1', validation_before: .7375, validation_after: .825,
    holdout_before: batch, holdout_after: structuredClone(batch), validation_before_details: batch, validation_after_details: batch,
    scoring: { function_weight: .65, preference_weight: .35, gate: 'code_structure',
      checks: { code_structure: 'Java 구조 검사. 컴파일 검사는 아님.', route: 'GET 경로', validation: '음수 거절', calculation: '세 입력 계산식' },
      preferences: { explanation: '60자 이상과 줄 시작 번호. 제목 안 번호는 현재 검사에서 인식하지 않음.', comments: '주석 2개 이상.', structure: '클래스 2개 이상.', output: '변경 부분 또는 새 구현 전체 코드.' } } };
}

test('74점은 항목별 확인 결과를 먼저 보여주고 계산 비중·실측·원본 유지 이유를 펼쳐 확인한다', async () => {
  const preferences = { explanation: 'steps', comments: 'detailed', structure: 'modular', output: 'changes' };
  const profile = { ...PROFILE, language: 'Java', framework: 'Spring Boot', preferences };
  const api = backend(profile, '선택한 Spring Boot 원본');
  api.state.environments = { spring_boot: { enabled: true } };
  api.state.report = springInspectionReport(); api.state.changed = false;
  const ui = await mount('https://example.test/', 'coding', api.fetch);
  try {
    await openResult(ui, 'Java', 'Spring Boot', preferences); await ui.click('실제 AI로 GEPA 개선 시작');
    const area = document.querySelector('.coding-evaluation');
    assert.ok(area.querySelector('[role="status"]').textContent.includes('추가 개선 확인 안 됨'));
    assert.ok(area.querySelector('[role="status"]').textContent.includes('탈락한 후보의 점수가 아니에요'));
    const overview = area.querySelector('.coding-evaluation-overview').textContent;
    assert.ok(overview.includes('8/8개 확인 → 8/8개 확인'));
    assert.ok(overview.includes('2/8개 확인 → 2/8개 확인'));
    const rows = [...area.querySelectorAll('tbody tr')];
    assert.ok(rows[0].textContent.includes('과정과 이유를 단계별로'));
    assert.ok(rows[0].textContent.includes('0/2개 확인'));
    assert.ok(rows[3].textContent.includes('2/2개 확인'));
    assert.ok(rows[3].textContent.includes('유지'));
    const scoreDetails = area.querySelector('.coding-evaluation-score');
    assert.equal(scoreDetails.open, false, 'numbers are secondary and collapsed');
    await ui.act(async () => scoreDetails.querySelector('summary').click());
    assert.ok(scoreDetails.textContent.includes('기능 65 + 답변 방식 8.75'));
    assert.ok(scoreDetails.textContent.includes('73.75점'));
    await ui.act(async () => area.querySelector('.coding-evaluation-details summary').click());
    assert.ok(area.textContent.includes('제목 안 번호는 현재 검사에서 인식하지 않음'));
    assert.ok(area.textContent.includes('Java 행·블록 주석 1개'));
    assert.ok(area.textContent.includes('반영된 표현도 놓칠 수 있어요'));
    assert.equal(button('개선 후보를 새로 보관할게요'), undefined);
    assert.equal(api.state.records.length, 1);
  } finally { await ui.close(); }
});

test('총점이 같아도 항목별 증가·감소를 구분하며 과거에 없는 검사 기록은 추측하지 않는다', async () => {
  const api = backend(); api.state.report = springInspectionReport();
  for (const task of api.state.report.holdout_after.tasks) task.preferences = { explanation: true, comments: false, structure: false, output: false };
  delete api.state.report.validation_before_details; delete api.state.report.validation_after_details;
  const ui = await mount('https://example.test/', 'coding', api.fetch);
  try {
    await openResult(ui); await ui.click('실제 AI로 GEPA 개선 시작');
    const area = document.querySelector('.coding-evaluation');
    const rows = [...area.querySelectorAll('tbody tr')];
    assert.ok(rows[0].textContent.includes('확인 증가'));
    assert.ok(rows[3].textContent.includes('확인 감소'));
    assert.ok(area.querySelector('[role="status"]').textContent.includes('추가 개선 확인 안 됨'));
    await ui.click('후보 선택 과제 2개');
    assert.equal(area.querySelector('table'), null);
    assert.ok(area.textContent.includes('과거 점수에서 반영 여부를 추측하지 않습니다'));
    await ui.click('별도 확인 과제 2개');
    assert.ok(area.querySelector('table'));
  } finally { await ui.close(); }
});

test('v2는 주석·구성을 직접 확인으로 표시하고 실제 답변의 내 판단을 새 후보에 함께 보관한다', async () => {
  const api = backend(); api.state.report = springInspectionReport();
  api.state.report.version = 'fastapi-static-v2';
  api.state.report.scoring.preference_keys = ['explanation','output'];
  api.state.report.scoring.manual_preferences = ['comments','structure'];
  const original = structuredClone(api.state.records[0]);
  const ui = await mount('https://example.test/', 'coding', api.fetch);
  try {
    await openResult(ui); await ui.click('실제 AI로 GEPA 개선 시작');
    const rows = [...document.querySelectorAll('.coding-evaluation tbody tr')];
    assert.ok(rows[1].textContent.includes('직접 확인') && rows[1].textContent.includes('자동 점수 제외'));
    assert.ok(document.querySelector('.coding-review-support').textContent.includes('이전 v1'));
    await ui.act(async () => document.querySelector('.fastapi-gepa-examples summary').click());
    const group = document.querySelector('[aria-label="후보 답변 주석 정도 확인"]');
    assert.equal(group.querySelectorAll('[aria-pressed="true"]').length, 0);
    await ui.act(async () => [...group.querySelectorAll('button')].find(button => button.textContent === '잘 맞아요').click());
    await ui.click('인쇄 요금');
    await ui.act(async () => [...document.querySelectorAll('[aria-label="기존 답변 코드 구성 확인"] button')].find(button => button.textContent === '판단 보류').click());
    await ui.click('대여 견적');
    assert.equal(document.querySelector('[aria-label="후보 답변 주석 정도 확인"] [aria-pressed="true"]').textContent, '잘 맞아요');
    await ui.click('개선 후보를 새로 보관할게요'); await ui.fill('#fastapi-gepa-save-title', '직접 확인한 후보'); await ui.click('개선 후보를 새 항목으로 저장');
    const saved = api.state.records[0];
    assert.deepEqual(saved.coding_optimization.human_review, { one: { candidate: { comments:'match' } }, two: { original: { structure:'unsure' } } });
    assert.deepEqual(api.state.records[1], original);
    await ui.click('저장한 개선 후보 열기');
    assert.ok(document.querySelector('.saved-human-review').textContent.includes('주석 정도 잘 맞아요'));
    assert.ok(document.querySelector('.saved-human-review').textContent.includes('코드 구성 판단 보류'));
  } finally { await ui.close(); }
});

test('C++도 받은 실제 답변을 확인하며 편집하면 이전 판단을 초기화하고 GEPA 지원 범위를 구분한다', async () => {
  const api = backend({ ...PROFILE, language:'C++', framework:'' }, 'C++ 개인 지침');
  const ui = await mount('https://example.test/', 'coding', api.fetch);
  try {
    await openResult(ui, 'C++', '프레임워크 없이');
    assert.equal(document.querySelector('.fastapi-optimization'), null);
    await ui.act(async () => document.querySelector('.coding-answer-review summary').click());
    assert.ok(document.querySelector('.coding-answer-review').textContent.includes('GEPA 자동 개선은 아직 지원하지 않습니다'));
    await ui.fill('#coding-received-answer','### 1. 입력 확인\n```cpp\n// 입력의 범위를 먼저 확인합니다.\nint main() {}\n```');
    await ui.click('답변 단서 확인하기');
    assert.equal(api.state.calls.find(call => call.path.endsWith('/review')).body.profile.language,'C++');
    const review = document.querySelector('[aria-label="붙여 넣은 답변 주석 정도 확인"]');
    await ui.act(async () => [...review.querySelectorAll('button')].find(button => button.textContent === '보완이 필요해요').click());
    assert.ok(document.querySelector('.coding-answer-review').textContent.includes('1/4항목'));
    await ui.fill('#coding-received-answer','수정한 답변');
    assert.equal(document.querySelector('.coding-human-review'), null);
    assert.equal(api.state.calls.filter(call => call.path === BASE && call.method).length,0);
    assert.equal(api.state.records.length,1);
  } finally { await ui.close(); }
});

test('JavaScript·TypeScript의 React/Express도 전후 비교·새 항목 저장·재사용으로 이어진다', async () => {
  for (const [language, framework, kind] of [
    ['JavaScript','React','javascript_react'], ['TypeScript','React','typescript_react'],
    ['JavaScript','Express','javascript_express'], ['TypeScript','Express','typescript_express'],
  ]) {
    const profile = { ...PROFILE, language, framework };
    const original = `${language} ${framework} 원본 지침`;
    const api = backend(profile,original);
    api.state.environments = { [kind]: { enabled:true } };
    const snapshot = structuredClone(api.state.records[0]);
    const ui = await mount('https://example.test/','coding',api.fetch);
    try {
      await openResult(ui,language,framework);
      assert.ok(document.querySelector('.fastapi-optimization .coding-kicker').textContent.includes(`${language} · ${framework} + GEPA`));
      assert.equal(api.state.calls.filter(call => call.path === BASE && call.method).length,0);
      await ui.click('실제 AI로 GEPA 개선 시작');
      const sent = api.state.calls.find(call => call.path === BASE && call.method);
      assert.equal(sent.body.profile.language,language); assert.equal(sent.body.profile.framework,framework);
      await ui.click('개선 후보를 새로 보관할게요');
      await ui.fill('#fastapi-gepa-save-title',`${framework} 새 후보`); await ui.click('개선 후보를 새 항목으로 저장');
      assert.deepEqual(api.state.records[1],snapshot);
      await ui.click('저장한 개선 후보 열기');
      await ui.fill('#preference-task','다음 개발 작업');
      assert.ok(document.querySelector('#preference-request').value.includes(GUIDANCE));
      assert.ok(document.querySelector('.saved-coding-profile').textContent.includes(`${language} · ${framework}`));
    } finally { await ui.close(); }
  }
});

test('웹 GEPA가 꺼졌거나 구형 서버면 다른 환경의 활성화 상태로 우회하지 않는다', async () => {
  const api = backend({ ...PROFILE,language:'JavaScript',framework:'Express' },'Express 원본');
  api.state.environments = { fastapi:{enabled:true}, javascript_express:{enabled:false,reason:'정적 검사 도구를 준비해 주세요.'} };
  const ui = await mount('https://example.test/','coding',api.fetch);
  try {
    await openResult(ui,'JavaScript','Express');
    assert.ok(button('실제 AI로 GEPA 개선 시작').disabled);
    assert.ok(document.querySelector('.fastapi-optimization').textContent.includes('정적 검사 도구'));
    assert.equal(api.state.calls.filter(call => call.path === BASE && call.method).length,0);
  } finally { await ui.close(); }
});

test('환경별 GEPA는 전후 비교·별도 과제 직접 확인·새 항목 저장·다음 작업 재사용으로 이어진다', async () => {
  for (const [language, framework, kind] of [['Python','Flask','flask'],['Python','Django','django'],['JavaScript','Vue','javascript_vue'],['TypeScript','Vue','typescript_vue'],['JavaScript','Next.js','javascript_nextjs'],['TypeScript','Next.js','typescript_nextjs'],['TypeScript','NestJS','typescript_nestjs']]) {
    const profile = { ...PROFILE,language,framework };
    const original = `${language} ${framework} 원본 지침`;
    const api = backend(profile,original);
    api.state.environments = { [kind]:{enabled:true,evaluation_scope:`${framework}의 경로·입력·응답을 확인합니다.`} };
    const snapshot = structuredClone(api.state.records[0]);
    const ui = await mount('https://example.test/','coding',api.fetch);
    try {
      await openResult(ui,language,framework);
      assert.ok(document.querySelector('.fastapi-optimization .coding-kicker').textContent.includes(`${language} · ${framework} + GEPA`));
      assert.ok(document.querySelector('.fastapi-optimization').textContent.includes('경로·입력·응답'));
      assert.equal(api.state.calls.filter(call => call.path === BASE && call.method).length,0);
      await ui.click('실제 AI로 GEPA 개선 시작');
      assert.equal(document.querySelector('#fastapi-gepa-original').value,original);
      await ui.act(async () => document.querySelector('.fastapi-gepa-examples summary').click());
      await ui.act(async () => [...document.querySelectorAll('[aria-label="후보 답변 주석 정도 확인"] button')].find(button => button.textContent === '잘 맞아요').click());
      await ui.click('개선 후보를 새로 보관할게요');
      await ui.fill('#fastapi-gepa-save-title',`${framework} 새 후보`); await ui.click('개선 후보를 새 항목으로 저장');
      assert.deepEqual(api.state.records[1],snapshot);
      assert.equal(api.state.records[0].coding_optimization.human_review.one.candidate.comments,'match');
      await ui.click('저장한 개선 후보 열기'); await ui.fill('#preference-task','다음 API 작업');
      assert.ok(document.querySelector('#preference-request').value.includes(GUIDANCE));
      assert.ok(document.querySelector('.saved-coding-profile').textContent.includes(`${language} · ${framework}`));
    } finally { await ui.close(); }
  }
});

test('각 환경은 다른 환경이 켜져 있어도 본인 설정이 없거나 꺼지면 시작하지 않는다', async () => {
  for (const [language,framework] of [['Python','Flask'],['Python','Django'],['JavaScript','Vue'],['TypeScript','Vue'],['JavaScript','Next.js'],['TypeScript','Next.js'],['TypeScript','NestJS']]) {
    const api = backend({ ...PROFILE,language,framework },`${framework} 원본`);
    api.state.environments = { fastapi:{enabled:true} };
    const ui = await mount('https://example.test/','coding',api.fetch);
    try {
      await openResult(ui,language,framework);
      assert.ok(button('실제 AI로 GEPA 개선 시작').disabled);
      assert.equal(api.state.calls.filter(call => call.path === BASE && call.method).length,0);
    } finally { await ui.close(); }
  }
});
