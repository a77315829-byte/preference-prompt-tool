import test from 'node:test';
import assert from 'node:assert/strict';
import { mount } from '../../../test-support/appHarness.js';
import { CODING_CHOICES } from './codingOptions.js';
import { differentPreferences, formatSeconds, observedSeconds } from './workflowApi.js';

const profile = { language: 'TypeScript', framework: 'React', extra: '',
  preferences: { explanation: 'brief', comments: 'essential', structure: 'compact', output: 'changes' } };
const button = text => [...document.querySelectorAll('button')].find(b => b.textContent.trim() === text);

test('미측정과 0초를 구분하고 진행 중인 조건에만 서버 경과 시간을 더한다', () => {
  assert.equal(formatSeconds(null), '미측정'); assert.equal(formatSeconds(0), '0분 0초');
  assert.deepEqual(differentPreferences(profile, { ...profile, preferences: { ...profile.preferences, structure: 'modular' } }), ['structure']);
  const trial = { server_now: 110, active: { arm: 'general', phase: 'edit', since: 100 },
    arms: { general: { seconds: { edit: 5, setup: 8 } } } };
  assert.equal(observedSeconds(trial, 'general', 'edit', 2), 17);
  assert.equal(observedSeconds(trial, 'general', 'setup', 2), 8);
});

test('React 지침 → 팀 차이 직접 선택 → 내보내기 → 고정 작업 비교·타이머', async () => {
  let team = null; let trial = null; let resolved; let exportBody; let trialBody;
  const response = data => ({ ok: true, status: 200, json: async () => structuredClone(data) });
  const ui = await mount('https://example.test/', 'coding', async (path, options) => {
    const body = options.body ? JSON.parse(options.body) : {};
    if (path === '/api/auth/me') return response({ user: { id: 1, username: 'alice' } });
    if (path === '/api/teams') return response({ teams: team ? [{ ...team, members: 1 }] : [] });
    if (path === '/api/coding-instructions/preview') return response({ draft: { profile: body.profile, prompt: '개인 TypeScript React 지침' } });
    if (path === '/api/coding-work/resolve') {
      resolved = { profile: body.profile, prompt: body.teamSelection ? '팀 규칙 유지한 React 지침' : '개인 TypeScript React 지침',
        snapshot: body.teamSelection ? 'team-snapshot' : 'personal-snapshot',
        team_context: body.teamSelection ? { name: team.name, revision: 2 } : null };
      return response({ draft: resolved });
    }
    if (path === '/api/coding-work/teams') {
      team = { code: 'team-new', name: body.name, profile: body.profile, rules: body.rules, revision: 1,
        domain_key: 'coding_profile', members: ['alice'], is_member: true, can_manage: true, protected: true, invite_open: true, invite_until: 9999999999 };
      return response({ team });
    }
    if (path === '/api/coding-work/teams/team-new/update') {
      team = { ...team, profile: body.profile, rules: body.rules, revision: 2 }; return response({ team });
    }
    if (path === '/api/coding-work/exports') {
      exportBody = body; return response({ export: { path: 'AGENTS.md', filename: 'AGENTS.md', content: body.existing + '\n' + body.prompt,
        diff: '+ 팀 규칙 유지한 React 지침', scope: '저장소 적용', verification: '도구에서 적용 확인' } });
    }
    if (path === '/api/coding-work/trials' && options.method !== 'POST') return response({ trials: trial ? [trial] : [] });
    if (path === '/api/coding-work/trials') {
      trialBody = body;
      trial = { ...body, id: 'trial-1', revision: 1, order: ['general', 'selected'], active: null, server_now: 100,
        preference: 'unselected', preference_reason: '', prompts: { general: '일반 고정', selected: resolved.prompt },
        comparison: { seconds: { general: null, selected: null }, timing_complete: false, both_passed: false, both_checked: false },
        arms: Object.fromEntries(['general', 'selected'].map(a => [a, { seconds: { setup: 0, edit: 0 }, timed: { setup: false, edit: false },
          outcome: 'unverified', evidence: '', answer: '', passed_tests: null, total_tests: null }])) };
      return response({ trial });
    }
    if (path === '/api/coding-work/trials/trial-1/timer') {
      assert.equal(body.revision, trial.revision);
      trial = { ...trial, revision: trial.revision + 1, active: body.operation === 'start' ? { arm: body.arm, phase: body.phase, since: 100 } : null };
      return response({ trial });
    }
    return null;
  });
  try {
    await ui.act(async () => document.querySelector('[aria-label="코딩 도움 선택"]').click());
    await ui.act(async () => document.querySelector('.selection-button').click());
    for (const label of ['TypeScript 선택', 'React 선택']) await ui.act(async () => document.querySelector(`[aria-label="${label}"]`).click());
    await ui.click('설정 카드로 직접 고를게요');
    for (const [key, value] of Object.entries(profile.preferences)) {
      const label = `${CODING_CHOICES[key].label}: ${CODING_CHOICES[key].options[value]}`;
      await ui.act(async () => document.querySelector(`[aria-label="${label}"]`).click());
    }
    await ui.click('내 선택 확인하기 →'); await ui.click('내 선택으로 프롬프트 만들기');
    await ui.fill('.coding-workflow details input', 'React 개발팀');
    await ui.fill('.coding-workflow details textarea', '기존 API 유지');
    await ui.click('팀 기준 만들기');
    await ui.fill('.coding-work-preview details select', 'steps');
    await ui.click('팀 기준 새 버전 저장');
    assert.ok(button('이번 작업용 지침 만들기').disabled);
    const chooser = document.querySelector('.coding-work-table select');
    await ui.fill(`[aria-label="${chooser.getAttribute('aria-label')}"]`, 'team');
    await ui.click('이번 작업용 지침 만들기');
    assert.match(document.querySelector('.coding-work-selected').textContent, /React 개발팀 2판/);
    await ui.click('2. 도구에 적용');
    await ui.click('파일과 변경 내용 확인');
    assert.equal(exportBody.prompt, '팀 규칙 유지한 React 지침');
    assert.ok(button('AGENTS.md 내려받기'));
    await ui.click('3. 작업 시간·기능 비교');
    const form = document.querySelector('.coding-workflow form');
    const fields = form.querySelectorAll('input, textarea');
    for (const [i, value] of ['검색 초기화 버그', '동일 도구', '동일 모델', '검색 초기화 시 목록 복구', '커밋 abc123, 타입·회귀 검사'].entries()) {
      fields[i].setAttribute('data-test-field', String(i)); await ui.fill(`[data-test-field="${i}"]`, value);
    }
    await ui.act(async () => form.dispatchEvent(new ui.dom.window.Event('submit', { bubbles: true, cancelable: true })));
    assert.equal(trialBody.snapshot, 'team-snapshot'); assert.equal(trialBody.teamSelection.choices.explanation, 'team');
    assert.match(document.querySelector('.coding-work-times').textContent, /미측정/);
    await ui.click('준비 시간 재기');
    assert.ok(button('1. 팀 기준과 연결').disabled); assert.ok(button('2. 도구에 적용').disabled);
    await ui.click('멈추고 시간 저장');
    assert.equal(button('2. 도구에 적용').disabled, false);
    assert.equal(document.querySelectorAll('.coding-work-arm').length, 2);
  } finally { await ui.close(); }
});
