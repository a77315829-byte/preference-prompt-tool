import assert from 'node:assert/strict';
import fs from 'node:fs';
import { mount } from '../../frontend/test-support/appHarness.js';
import { CODING_CHOICES } from '../../frontend/src/features/coding-instructions/codingOptions.js';

const examples = JSON.parse(fs.readFileSync(new URL('./examples.json', import.meta.url), 'utf8'));
const profiles = [];
const ok = data => ({ok: true, status: 200, json: async () => structuredClone(data)});
let user = 200;
async function setup(name) {
  const id = ++user;
  const ui = await mount('http://localhost/', 'coding', async (path, options) => {
    if (path === '/api/auth/me') return ok({user: {id, username: `audit-${id}`}});
    if (path === '/api/preferences') return ok({preferences: []});
    if (path === '/api/coding-instructions/examples') return ok({examples});
    if (path === '/api/coding-instructions/preview') {
      const profile = JSON.parse(options.body).profile;
      profiles.push({name, profile});
      return ok({draft: {profile, prompt: 'audit generated prompt'}});
    }
    if (path === '/api/coding-instructions/optimizations') return ok({enabled: false});
    if (path === '/api/coding-instructions/optimizations/recent') return ok({jobs: []});
    return null;
  });
  ui.press = async (selector, index = 0) => {
    const button = document.querySelectorAll(selector)[index];
    assert.ok(button, selector); assert.equal(button.disabled, false, selector);
    await ui.act(async () => button.click());
  };
  ui.enter = async () => { await ui.press('[aria-label="코딩 도움 선택"]'); await ui.press('.selection-button'); };
  await ui.enter(); await ui.press('[aria-label="Python 선택"]'); await ui.press('[aria-label="FastAPI 선택"]');
  await ui.click('코드 예시 비교 시작하기 →');
  return ui;
}
async function fillRemaining(ui) {
  for (const field of document.querySelectorAll('.coding-preference-buttons')) {
    if (!field.querySelector('[aria-pressed="true"]')) await ui.act(async () => field.querySelector('button').click());
  }
}
async function choose(ui, round, value) {
  if (value === null) await ui.click('예시는 보류할게요');
  else await ui.press('.coding-option-select', examples.pairs[round].options.findIndex(option => option.value === value));
}

for (let count = 1; count <= 8; count++) {
  const ui = await setup(`prefix-${count}`);
  try {
    for (let round = 0; round < count; round++) {
      await choose(ui, round, Object.keys(CODING_CHOICES[examples.pairs[round].axis].options)[0]);
      if (round + 1 < count) await ui.click('이 선택으로 다음 →');
    }
    await ui.click('여기까지 비교하고 선택 확인하기');
    assert.match(document.querySelector('[aria-label="반복 비교에서 확인한 신호"]').textContent, new RegExp(`${count}회 비교`));
    assert.equal(document.querySelectorAll('.coding-preference-buttons [aria-pressed="true"]').length, Math.min(count, 4));
    await fillRemaining(ui); await ui.click('내 선택으로 프롬프트 만들기');
    assert.equal(profiles.at(-1).profile.comparison.rounds.length, count);
    console.log(`PASS finish after ${count} comparisons`);
  } finally { await ui.close(); }
}

{
  const ui = await setup('mixed-skipped');
  try {
    for (let round = 0; round < 8; round++) {
      const axis = examples.pairs[round].axis;
      const value = axis === 'comments' ? null : Object.keys(CODING_CHOICES[axis].options)[axis === 'explanation' && round > 3 ? 1 : 0];
      await choose(ui, round, value);
      await ui.click(round === 7 ? '4가지 선택 확인하기 →' : '이 선택으로 다음 →');
    }
    assert.equal(document.querySelectorAll('.coding-preference-buttons [aria-pressed="true"]').length, 2);
    await fillRemaining(ui); await ui.click('내 선택으로 프롬프트 만들기');
    const summary = profiles.at(-1).profile.comparison.summary;
    assert.equal(summary.explanation.status, 'mixed'); assert.equal(summary.comments.status, 'unresolved');
    assert.equal(summary.structure.status, 'consistent'); assert.equal(summary.output.status, 'consistent');
    console.log('PASS skipped, mixed, and consistent axes stay distinct');
  } finally { await ui.close(); }
}

{
  const ui = await setup('back-navigation-cancel');
  try {
    for (let round = 0; round < 6; round++) { await ui.press('.coding-option-select'); await ui.click('이 선택으로 다음 →'); }
    await ui.click('내 선호 보관함'); await ui.click('시작하기'); await ui.enter();
    assert.match(document.querySelector('.coding-example-comparison').textContent, /7번째 비교/);
    await ui.press('.coding-axis-progress button', 1); await ui.press('.coding-option-select', 1);
    assert.equal(document.querySelectorAll('.coding-axis-progress button:not(:disabled)').length, 2);
    await ui.click('여기까지 비교하고 선택 확인하기');
    assert.match(document.querySelector('[aria-label="반복 비교에서 확인한 신호"]').textContent, /2회 비교/);
    await fillRemaining(ui); await ui.click('내 선택으로 프롬프트 만들기');
    await ui.click('선택 다시 바꾸기'); await ui.click('코드 예시를 보며 다시 고르기');
    await ui.press('.coding-option-select', 1); await ui.click('비교 취소');
    assert.match(document.querySelector('[aria-label="반복 비교에서 확인한 신호"]').textContent, /2회 비교/);
    await ui.press('.coding-stepper button', 2);
    assert.equal(document.querySelector('#coding-instructions-prompt').value, 'audit generated prompt');
    await ui.click('선택 다시 바꾸기'); await ui.click('코드 예시를 보며 다시 고르기');
    assert.equal(document.querySelectorAll('.coding-option-select[aria-pressed="true"]').length, 0);
    await ui.click('비교 취소');
    console.log('PASS back edit invalidates later answers; menu restores; cancellation preserves prompt; re-entry starts fresh');
  } finally { await ui.close(); }
}
fs.writeFileSync(new URL('./profiles.json', import.meta.url), JSON.stringify(profiles, null, 2));
