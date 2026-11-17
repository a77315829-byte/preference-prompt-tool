// Local production build, isolated browser contexts, synthetic data only.
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'C:/Program Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1110-778-0_26.1110.778.0_x64__3k8sg7r9htsxt/dependencies/node/node_modules/playwright');
const BASE = 'http://127.0.0.1:18767';
const RUN = path.resolve(__dirname, '../../../tmp/weekly-20261117/browser');
fs.mkdirSync(RUN, { recursive: true });
const results = [], errors = [], external = [];
let browser;
async function step(name, fn) {
  try { await fn(); results.push({ name, pass: true }); console.log(`PASS ${name}`); }
  catch (error) { results.push({ name, pass: false, error: error.message }); throw error; }
}
async function context() {
  const ctx = await browser.newContext({ viewport: { width: 1360, height: 1020 }, locale: 'ko-KR', reducedMotion: 'reduce' });
  await ctx.route('**/*', route => {
    const url = new URL(route.request().url());
    if (url.origin === BASE || ['data:', 'blob:'].includes(url.protocol)) return route.continue();
    external.push(url.origin + url.pathname); return route.abort();
  });
  ctx.setDefaultTimeout(15000);
  return ctx;
}
async function main() {
  browser = await chromium.launch({ headless: true, executablePath: process.env.CHROMIUM_PATH || 'C:/Users/Laptop_PC/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe' });
  const alice = await context(), bob = await context();
  const page = await alice.newPage();
  page.on('pageerror', error => errors.push(error.message));
  const source = 'The launch moved to Friday. Testing remains unfinished. Funding depends on approval.';
  let state;
  await step('01 guest summary comparison completes through the real UI', async () => {
    assert.equal((await (await alice.request.get(BASE + '/api/health')).json()).live, false);
    await page.goto(BASE);
    await page.getByRole('button', { name: '문서 요약 선택', exact: true }).click();
    await page.locator('.category-selection .selection-button').click();
    await page.locator('.task-input').fill(source);
    const created = page.waitForResponse(r => r.url().endsWith('/api/sessions') && r.request().method() === 'POST');
    await page.getByRole('button', { name: '이 내용으로 시작', exact: true }).click();
    state = (await (await created).json()).session;
    for (let i = 0; !state.done && i < 8; i++) {
      const changed = page.waitForResponse(r => r.url().endsWith(`/api/sessions/${state.session_id}/choices`));
      await page.locator('.comparison-option').first().click();
      state = (await (await changed).json()).session;
    }
    assert.equal(state.done, true);
    await page.locator('.summary-contract').waitFor();
    await page.screenshot({ path: path.join(RUN, 'summary-result.png') });
  });
  await step('02 another guest cannot read or mutate a known session ID', async () => {
    assert.equal((await bob.request.get(`${BASE}/api/sessions/${state.session_id}`)).status(), 404);
    assert.equal((await bob.request.post(`${BASE}/api/sessions/${state.session_id}/undo`, { data: {} })).status(), 404);
    assert.equal((await alice.request.get(`${BASE}/api/sessions/${state.session_id}`)).status(), 200);
  });
  const stamp = Date.now();
  await step('03 signing in promotes only the same guest browser session', async () => {
    assert.equal((await alice.request.post(BASE + '/api/auth/signup', { data: { username: `a${stamp}`, password: 'Local-test-only-142!' } })).status(), 200);
    assert.equal((await alice.request.get(`${BASE}/api/sessions/${state.session_id}`)).status(), 200);
    assert.equal((await bob.request.post(BASE + '/api/auth/signup', { data: { username: `b${stamp}`, password: 'Local-test-only-142!' } })).status(), 200);
    const response = await bob.request.get(`${BASE}/api/sessions/${state.session_id}`);
    assert.equal(response.status(), 404);
    assert.ok(!(await response.text()).includes(source));
  });
  await step('04 logout revokes session and focus removes the result and source', async () => {
    assert.equal((await alice.request.post(BASE + '/api/auth/logout', { data: {} })).status(), 200);
    await page.evaluate(() => window.dispatchEvent(new Event('focus')));
    await page.locator('.task-input').waitFor();
    assert.equal(await page.locator('.task-input').inputValue(), '');
    assert.equal(await page.locator('.summary-contract').count(), 0);
    assert.ok(!(await page.locator('body').innerText()).includes(source));
    await page.screenshot({ path: path.join(RUN, 'revoked-result.png') });
  });
  await step('05 fixed TTL clears the active UI without a user action', async () => {
    await page.locator('.task-input').fill(source);
    const created = page.waitForResponse(r => r.url().endsWith('/api/sessions') && r.request().method() === 'POST');
    await page.getByRole('button', { name: '이 내용으로 시작', exact: true }).click();
    const next = (await (await created).json()).session;
    assert.ok(next.expires_in_seconds > 0 && next.expires_in_seconds <= 40, 'Use VERIFY_SESSION_TTL_HOURS=0.01 for this disposable server');
    await page.locator('.comparison-option').first().waitFor();
    await page.locator('.task-input').waitFor({ timeout: 45000 });
    assert.equal(await page.locator('.task-input').inputValue(), '');
    assert.equal((await alice.request.get(`${BASE}/api/sessions/${next.session_id}`)).status(), 404);
  });
  await step('06 React style API uses v2 and preserves both final languages', async () => {
    const created = await bob.request.post(BASE + '/api/sessions', { data: { domainKey: 'coding', sourceText: 'A button that counts clicks.', totalRounds: 1 } });
    assert.equal(created.status(), 201);
    const coding = (await created.json()).session;
    assert.match(coding.domain_path.replaceAll('\\', '/'), /domains\/coding\/v2\.yaml$/);
    const finished = await bob.request.post(`${BASE}/api/sessions/${coding.session_id}/choices`, { data: { pairId: coding.pair.pair_id, chosen: 'a' } });
    assert.equal(finished.status(), 200);
    const result = (await finished.json()).session;
    assert.equal(result.done, true);
    assert.ok(result.prompts.en && result.prompts.ko);
  });
  assert.deepEqual(errors, []);
  assert.deepEqual(external, []);
}
main().catch(error => { console.error(error); process.exitCode = 1; }).finally(async () => {
  fs.writeFileSync(path.join(RUN, 'results.json'), JSON.stringify({ results, errors, external, paid_model_api_calls: 0 }, null, 2));
  await browser?.close();
});
