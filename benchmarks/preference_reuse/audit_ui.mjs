// Existing React appHarness, offline fetch transport, real Python functions/SQLite.
// No HTTP server, browser screenshot, external API, or live AI assertions.
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { mount } from '../../frontend/test-support/appHarness.js';
import { CODING_CHOICES } from '../../frontend/src/features/coding-instructions/codingOptions.js';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '../..');
const python = [path.join(root, '.venv/Scripts/python.exe'), path.join(root, '.venv/bin/python')].find(existsSync);
assert.ok(python, 'Use the existing project .venv Python interpreter');
const run = path.join(here, `ui-${Date.now()}`);
mkdirSync(run);
const database = path.join(run, 'ui.db');
const report = { scope: 'React/JSDOM + replaced fetch + actual Python functions via stdin/stdout. No HTTP or human usability study.', python, scenarios: [], failures: [] };
const files = ['frontend/src/features/coding-instructions/CodingInstructionsSection.jsx',
  'frontend/src/features/coding-instructions/CodingEnvironmentPicker.jsx',
  'frontend/src/features/preferences/PreferencesSection.jsx',
  'frontend/src/features/preferences/SavePreferencePanel.jsx'];
const hashes = () => Object.fromEntries(files.map(file => [file, createHash('sha256').update(readFileSync(path.join(root, file))).digest('hex')]));
report.sourceSha256Before = hashes();

function bridge(operation, body = {}, id) {
  const result = spawnSync(python, ['-B', path.join(here, 'backend_bridge.py')], {
    input: JSON.stringify({ database, operation, body, id }), encoding: 'utf8',
    env: { ...process.env, PYTHONUTF8: '1' }, cwd: root, windowsHide: true, timeout: 30000,
  });
  assert.equal(result.status, 0, result.error?.message || result.stderr);
  const data = JSON.parse(result.stdout);
  report.pythonRuntime = data.auditRuntime;
  delete data.auditRuntime;
  return data;
}
const response = data => ({ ok: true, status: 200, json: async () => structuredClone(data) });
const picks = { explanation: 'steps', comments: 'detailed', structure: 'modular', output: 'changes' };

function server() {
  const state = { requests: [], saved: [], previews: [], bank: null };
  return { state, fetch: async (url, options = {}) => {
    const body = options.body ? JSON.parse(options.body) : {};
    state.requests.push({ url, method: options.method || 'GET', body });
    if (url === '/api/auth/me') return response({ user: { id: 1, username: 'audit' }, signupOpen: true });
    if (url === '/api/health') return response({ live: false, liveConfigured: false });
    if (url === '/api/teams') return response({ teams: [] });
    if (url === '/api/coding-instructions/optimizations') return response({ enabled: false, reason: 'Offline audit' });
    if (url === '/api/coding-instructions/optimizations/recent') return response({ jobs: [] });
    if (url === '/api/coding-instructions/examples') {
      const data = bridge('examples', body); state.bank = data.examples; return response(data);
    }
    if (url === '/api/coding-instructions/preview') {
      const data = bridge('preview', body); state.previews.push(data.draft); return response(data);
    }
    if (url === '/api/preferences') {
      if (options.method === 'POST') {
        const data = bridge('create', body); state.saved.push(data.preference); return response(data);
      }
      return response(bridge('list'));
    }
    if (/^\/api\/preferences\/[^/]+$/.test(url)) {
      assert.equal(options.method, undefined, 'Audit must never update/delete a saved item');
      return response(bridge('get', {}, url.split('/').at(-1)));
    }
    if (url === '/api/coding-work/resolve') {
      const draft = body.profile ? bridge('preview', { profile: body.profile }).draft : (() => {
        const item = bridge('get', {}, body.preferenceId).preference;
        return { profile: item.coding_profile, prompt: item.prompt };
      })();
      return response({ draft: { ...draft, snapshot: 'offline-audit' } });
    }
    throw new Error(`Unexpected offline request ${url}`);
  } };
}

async function press(ui, label) {
  const button = [...document.querySelectorAll('button')].find(item => item.getAttribute('aria-label') === label);
  assert.ok(button, `Missing aria-label ${label}`); assert.equal(button.disabled, false);
  await ui.act(async () => button.click());
}
async function pick(ui, axis, value) {
  await press(ui, `${CODING_CHOICES[axis].label}: ${CODING_CHOICES[axis].options[value]}`);
}

for (const [language, framework, rounds] of [['Python', 'FastAPI', 4], ['JavaScript', 'React', 0], ['TypeScript', 'React', 8]]) {
  const api = server();
  const ui = await mount('https://example.test/', 'coding', api.fetch);
  const scenario = { language, framework, rounds, checkpoints: [] };
  const mark = text => scenario.checkpoints.push(text);
  try {
    await press(ui, '코딩 도움 선택');
    await ui.act(async () => document.querySelector('.selection-button').click());
    if (!document.querySelector(`[aria-label="${language} 선택"]`)) await ui.click('다른 언어도 보기 · 전체 14개');
    await press(ui, `${language} 선택`); await press(ui, `${framework} 선택`);
    if (rounds) {
      await ui.click('코드 예시 비교 시작하기 →');
      const notice = document.querySelector('.coding-example-scope').textContent;
      assert.ok(notice.includes(rounds === 4 ? 'FastAPI 전용' : 'TypeScript 기본 문법'));
      for (let index = 0; index < rounds; index += 1) {
        const pair = api.state.bank.pairs[index];
        const selected = pair.options.findIndex(option => option.value === picks[pair.axis]);
        await ui.act(async () => document.querySelectorAll('.coding-option-select')[selected].click());
        await ui.click(index === rounds - 1 && rounds === 4 ? '여기까지 비교하고 선택 확인하기' :
          index === rounds - 1 ? '4가지 선택 확인하기 →' : '이 선택으로 다음 →');
      }
    } else {
      await ui.click('설정 카드로 직접 고를게요');
      for (const [axis, value] of Object.entries(picks)) await pick(ui, axis, value);
      await ui.click('내 선택 확인하기 →');
    }
    await ui.click('내 선택으로 프롬프트 만들기');
    const generated = structuredClone(api.state.previews.at(-1));
    assert.deepEqual(generated.profile.preferences, picks);
    assert.equal(document.querySelector('#coding-instructions-prompt').value, generated.prompt);
    mark('UI selections reached real builder with correct final values');

    const firstTask = `${language} AUDIT_FIRST_TASK`; const secondTask = `${language} AUDIT_REPLACEMENT_TASK`;
    await ui.fill('#coding-new-task', firstTask);
    await ui.click('내 답변 방식 + 이번 작업 복사');
    assert.equal(ui.state.copied, `${generated.prompt}\n\n## 이번 작업 요청\n${firstTask}`);
    await ui.fill('#coding-new-task', secondTask);
    await ui.click('내 답변 방식 + 이번 작업 복사');
    assert.equal(ui.state.copied, `${generated.prompt}\n\n## 이번 작업 요청\n${secondTask}`);
    assert.ok(!ui.state.copied.includes(firstTask));
    await ui.click('프롬프트 복사');
    assert.equal(ui.state.copied, generated.prompt);
    mark('Replacing the task changes combined copy; instruction-only copy excludes both tasks');

    await ui.fill('#save-preference-title', `${language} audit original`);
    await ui.click('내 선호 보관함에 저장');
    const original = structuredClone(api.state.saved.at(-1));
    assert.equal(original.prompt, generated.prompt);
    assert.ok(!JSON.stringify(original).includes('AUDIT_FIRST_TASK'));
    assert.ok(!JSON.stringify(original).includes('AUDIT_REPLACEMENT_TASK'));
    assert.deepEqual(original.coding_profile, generated.profile);
    const createRequest = api.state.requests.find(row => row.url === '/api/preferences' && row.method === 'POST');
    assert.ok(!JSON.stringify(createRequest.body).includes('AUDIT_REPLACEMENT_TASK'));
    mark('Actual save payload and SQLite snapshot exclude transient tasks');

    await ui.click('저장한 지침 열기');
    assert.equal(document.querySelector('#preference-task').value, '');
    const reuseA = `${language} AUDIT_REUSE_A`; const reuseB = `${language} AUDIT_REUSE_B`;
    await ui.fill('#preference-task', reuseA); await ui.click('지침 + 새 작업 복사');
    assert.equal(ui.state.copied, `${original.prompt}\n\n---\n이번 개발 요청\n\n${reuseA}`);
    await ui.fill('#preference-task', reuseB); await ui.click('지침 + 새 작업 복사');
    assert.equal(ui.state.copied, `${original.prompt}\n\n---\n이번 개발 요청\n\n${reuseB}`);
    assert.ok(!ui.state.copied.includes(reuseA));
    assert.deepEqual(bridge('get', {}, original.id).preference, original);
    mark('Library reuse and replacement copy keep persisted original unchanged');

    ui.dom.window.confirm = () => true;
    await ui.click('이 설정으로 새 지침 만들기');
    assert.equal(document.querySelector(`[aria-label="${language} 선택"]`).getAttribute('aria-pressed'), 'true');
    await ui.click('저장한 선택으로 계속하기');
    await pick(ui, 'comments', 'essential');
    await ui.click('내 선택으로 프롬프트 만들기');
    const changed = structuredClone(api.state.previews.at(-1));
    assert.deepEqual(changed.profile.preferences, { ...picks, comments: 'essential' });
    assert.equal(document.querySelector('#coding-new-task').value, '');
    if (rounds) {
      assert.equal(changed.profile.comparison.choices.comments, null);
      assert.deepEqual(changed.profile.comparison.rounds, original.coding_profile.comparison.rounds);
      for (const axis of ['explanation', 'structure', 'output']) assert.equal(changed.profile.comparison.choices[axis], picks[axis]);
    }
    await ui.fill('#save-preference-title', `${language} audit comments changed`);
    await ui.click('내 선호 보관함에 저장');
    const child = api.state.saved.at(-1);
    assert.notEqual(child.id, original.id);
    assert.deepEqual(bridge('get', {}, original.id).preference, original);
    assert.equal(bridge('get', {}, child.id).preference.prompt, changed.prompt);
    mark('One-axis change has direct attribution; independent new item preserves old entry');
    assert.equal(ui.state.sessions, 0);
    assert.ok(!api.state.requests.some(row => /\/run$|\/choices$/.test(row.url)));
    scenario.requestCount = api.state.requests.length;
    scenario.status = 'passed';
  } catch (error) {
    scenario.status = 'failed'; scenario.error = error.stack;
    report.failures.push({ language, framework, rounds, error: error.stack });
    writeFileSync(path.join(run, `${language}-failure.html`), document.documentElement.outerHTML);
  } finally {
    report.scenarios.push(scenario);
    await ui.close();
  }
}
report.sourceSha256After = hashes();
report.sourceChangedDuringRun = JSON.stringify(report.sourceSha256Before) !== JSON.stringify(report.sourceSha256After);
writeFileSync(path.join(run, 'ui-results.json'), JSON.stringify(report, null, 2));
writeFileSync(path.join(here, 'latest-ui-run.txt'), run);
console.log(JSON.stringify({ run, ...report }, null, 2));
if (report.failures.length) process.exitCode = 1;
