// Real production UI, loopback API, synthetic account, no model requests.
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'C:/Program Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1110-778-0_26.1110.778.0_x64__3k8sg7r9htsxt/dependencies/node/node_modules/playwright');
const BASE = 'http://127.0.0.1:18769';
const OUT = path.resolve(__dirname, '../../../tmp/final-20261118/demo');
fs.mkdirSync(OUT, { recursive: true });
const results = [], errors = [], external = [], posts = [];
const SOURCE = 'The launch moved to Friday. Testing remains unfinished. Funding depends on approval.';
const NEXT = 'The library opens on Monday. Training begins on Tuesday. The team will review progress on Thursday.';
let browser, page, ctx, saved, contract;
async function step(name, fn) {
  try { await fn(); await page.waitForTimeout(5000); results.push({ name, pass: true }); console.log('PASS', name); }
  catch (error) { results.push({ name, pass: false, error: error.message }); throw error; }
}
async function postClick(button, endpoint, expected = 200) {
  const pending = page.waitForResponse(r => new URL(r.url()).pathname === endpoint && r.request().method() === 'POST');
  await button.click();
  const res = await pending;
  assert.equal(res.status(), expected, await res.text());
  return res.json();
}
async function startComparison(kind) {
  await page.goto(BASE);
  await page.getByRole('button', { name: kind === 'summary' ? '문서 요약 선택' : '코딩 도움 선택', exact: true }).click();
  if (kind === 'summary') await page.locator('.category-selection .selection-button').click();
  else await page.getByRole('button', { name: 'React 코드 스타일 비교', exact: true }).click();
  await page.locator('.task-input').fill(kind === 'summary' ? SOURCE : 'A TypeScript/React counter button.');
  let { session } = await postClick(page.getByRole('button', { name: '이 내용으로 시작', exact: true }), '/api/sessions', 201);
  for (let n = 0; !session.done && n < 8; n++) {
    ({ session } = await postClick(page.locator('.comparison-option').first(), `/api/sessions/${session.session_id}/choices`));
  }
  assert.equal(session.done, true);
  return session;
}
async function main() {
  browser = await chromium.launch({ headless: true, slowMo: 350, executablePath: process.env.CHROMIUM_PATH || 'C:/Users/Laptop_PC/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe' });
  ctx = await browser.newContext({ viewport: { width: 1440, height: 1080 }, locale: 'ko-KR', reducedMotion: 'reduce', recordVideo: { dir: OUT, size: {width:1440,height:1080} } });
  ctx.setDefaultTimeout(20000);
  await ctx.grantPermissions(['clipboard-read', 'clipboard-write'], { origin: BASE });
  await ctx.route('**/*', route => {
    const url = new URL(route.request().url());
    if (/\/api\/.*(optimize|\/run$)/.test(url.pathname)) return route.abort();
    if (url.origin === BASE || ['blob:', 'data:'].includes(url.protocol)) return route.continue();
    external.push(url.origin + url.pathname); return route.abort();
  });
  page = await ctx.newPage();
  page.on('pageerror', error => errors.push(error.message));
  page.on('request', req => { if (req.method() === 'POST') posts.push(new URL(req.url()).pathname); });
  const signup = await ctx.request.post(BASE + '/api/auth/signup', { data: { username: `demo_${Date.now()}`, password: 'Synthetic-demo-only-142!' } });
  assert.equal(signup.status(), 200);
  assert.equal((await (await ctx.request.get(BASE + '/api/health')).json()).live, false);
  await step('01 summary comparison completes and conflicting conditions block output', async () => {
    await startComparison('summary');
    await page.getByLabel('요약 분량', { exact: true }).selectOption('short');
    await page.getByLabel('원문 표현 방식', { exact: true }).selectOption('fully');
    await postClick(page.getByRole('button', { name: '조건 확인', exact: true }), '/api/summary-contract');
    await page.locator('.summary-contract-sentences summary').click();
    for (const checkbox of await page.locator('.summary-contract input[type="checkbox"]').all()) await checkbox.check();
    contract = await postClick(page.getByRole('button', { name: '조건 확인', exact: true }), '/api/summary-contract');
    assert.equal(contract.status, 'needs_resolution');
    assert.equal(await page.locator('.summary-contract .preference-save').count(), 0);
    await page.locator('.summary-contract-conflict').scrollIntoViewIfNeeded();
    await page.waitForTimeout(2500); await page.screenshot({ path: path.join(OUT, '01-summary-conflict.png') });
  });
  await step('02 explicit resolution saves the new instructions, excluding source and selected passages', async () => {
    await page.locator('.summary-contract input[value="expand"]').check();
    contract = await postClick(page.getByRole('button', { name: '조건 확인', exact: true }), '/api/summary-contract');
    assert.equal(contract.status, 'ready');
    assert.equal(contract.effective_profile.length, 'normal');
    const panel = page.locator('.summary-contract .preference-save');
    await panel.getByLabel('기억하기 쉬운 이름', { exact: true }).fill('시연 · 조건을 확인한 요약');
    saved = (await postClick(panel.getByRole('button', { name: '내 선호 보관함에 저장', exact: true }), '/api/preferences', 201)).preference;
    assert.equal(saved.prompt, contract.prompts.ko);
    for (const sentence of SOURCE.match(/[^.]+\./g)) assert.ok(!JSON.stringify(saved).includes(sentence.trim()));
    const ids = await page.locator('[id]').evaluateAll(nodes => nodes.map(n => n.id));
    assert.equal(new Set(ids).size, ids.length, 'Save forms need distinct label targets');
    await panel.scrollIntoViewIfNeeded();
    await page.waitForTimeout(2500); await page.screenshot({ path: path.join(OUT, '02-summary-saved.png') });
    await panel.getByRole('button', { name: '저장한 지침 열기', exact: true }).click();
  });
  await step('03 saved instructions combine with a new task without changing stored content', async () => {
    await page.getByRole('button', { name: '새 작업에 쓰기', exact: true }).click();
    await page.locator('#preference-task').fill(NEXT);
    const request = await page.locator('#preference-request').inputValue();
    assert.ok(request.includes(saved.prompt)); assert.ok(request.includes(NEXT)); assert.ok(!request.includes(SOURCE));
    assert.equal(await page.getByRole('button', { name: '이 지침으로 AI 실행', exact: true }).isDisabled(), true);
    await page.getByRole('button', { name: '지침 + 새 작업 복사', exact: true }).click();
    // Windows clipboard converts LF to CRLF; compare text with line endings normalized.
    assert.equal((await page.evaluate(() => navigator.clipboard.readText())).replaceAll('\r\n', '\n'), request);
    const stored = (await (await ctx.request.get(`${BASE}/api/preferences/${saved.id}`)).json()).preference;
    assert.equal(stored.prompt, saved.prompt); assert.equal(stored.revision, saved.revision);
    assert.ok(!JSON.stringify(stored).includes(NEXT));
    await page.locator('#preference-task').scrollIntoViewIfNeeded();
    await page.waitForTimeout(2500); await page.screenshot({ path: path.join(OUT, '03-new-task-reuse.png') });
  });
  await step('04 AI answer settings still generate and save a separate TypeScript React profile', async () => {
    await page.goto(BASE);
    await page.getByRole('button', { name: '코딩 도움 선택', exact: true }).click();
    await page.getByRole('button', { name: 'AI 답변 방식 설정', exact: true }).click();
    await page.getByRole('button', { name: 'TypeScript 선택', exact: true }).click();
    await page.getByRole('button', { name: 'React 선택', exact: true }).click();
    await page.getByRole('button', { name: '설정 카드로 직접 고를게요', exact: true }).click();
    await page.locator('.coding-preference-buttons').first().waitFor();
    assert.equal(await page.locator('.coding-preference-buttons').count(), 4);
    for (const group of await page.locator('.coding-preference-buttons').all()) await group.locator('button').first().click();
    await page.getByRole('button', { name: '내 선택 확인하기 →', exact: true }).click();
    await page.getByRole('button', { name: '내 선택으로 프롬프트 만들기', exact: true }).click();
    await page.locator('#coding-instructions-prompt').waitFor();
    assert.match(await page.locator('#coding-instructions-prompt').inputValue(), /TypeScript/);
    const panel = page.locator('.coding-instructions-result .preference-save');
    const coding = (await postClick(panel.getByRole('button', { name: '내 선호 보관함에 저장', exact: true }), '/api/preferences', 201)).preference;
    assert.equal(coding.coding_profile.language, 'TypeScript');
    assert.equal(coding.coding_profile.framework, 'React');
    assert.equal(Object.keys(coding.coding_profile.preferences).length, 4);
    await page.locator('.coding-result-banner').scrollIntoViewIfNeeded();
    await page.waitForTimeout(2500); await page.screenshot({ path: path.join(OUT, '04-coding-answer.png') });
  });
  await step('05 React style comparison retains v2 and both prompt languages', async () => {
    const session = await startComparison('coding');
    assert.match(session.domain_path.replaceAll('\\', '/'), /domains\/coding\/v2\.yaml$/);
    assert.ok(session.prompts.ko && session.prompts.en);
    assert.equal(session.axes.length, 3);
    await page.waitForTimeout(2500); await page.screenshot({ path: path.join(OUT, '05-react-style.png') });
  });
  await step('06 mobile layout and logout keep private results inaccessible', async () => {
    await page.setViewportSize({ width: 390, height: 844 });
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 2);
    assert.equal(overflow, false);
    const denied = await browser.newContext();
    assert.equal((await denied.request.get(`${BASE}/api/preferences/${saved.id}`)).status(), 401);
    await denied.close();
    assert.equal((await ctx.request.post(BASE + '/api/auth/logout', { data: {} })).status(), 200);
    await page.evaluate(() => window.dispatchEvent(new Event('focus')));
    await page.locator('.task-input').waitFor();
    assert.equal(await page.locator('.task-input').inputValue(), '');
    assert.equal((await ctx.request.get(`${BASE}/api/preferences/${saved.id}`)).status(), 401);
    await page.waitForTimeout(2500); await page.screenshot({ path: path.join(OUT, '06-logout-mobile.png') });
  });
  assert.deepEqual(errors, []); assert.deepEqual(external, []);
  assert.ok(posts.every(p => !/\/optimize|\/run$/.test(p)), 'No model or optimization endpoints');
}
main().catch(error => { console.error(error); process.exitCode = 1; }).finally(async () => {
  if (page && results.some(r => !r.pass)) await page.screenshot({ path: path.join(OUT, 'failure.png'), fullPage: true }).catch(() => {});
  fs.writeFileSync(path.join(OUT, 'browser.json'), JSON.stringify({ results, errors, external, posts, paid_model_api_calls: 0 }, null, 2));
  if (ctx) await ctx.close();
  if (page) await page.video()?.saveAs(path.join(OUT, 'Revealed_demo_20261118.webm'));
  await browser?.close();
});
