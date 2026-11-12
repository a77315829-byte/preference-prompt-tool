// Real production build + local HTTP; synthetic text and isolated browser storage.
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'C:/Program Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1110-778-0_26.1110.778.0_x64__3k8sg7r9htsxt/dependencies/node/node_modules/playwright');
const BASE = 'http://127.0.0.1:18763';
const RUN = path.resolve(__dirname, '../../../tmp/summary-policy-20261112/browser');
fs.mkdirSync(RUN, { recursive: true });
const results = [], errors = [], external = [], requests = [];
let browser, page;
async function step(name, fn) {
  try { await fn(); results.push({ name, pass: true }); console.log(`PASS ${name}`); }
  catch (e) { results.push({ name, pass: false, error: e.message }); throw e; }
}
async function postByClick(button, endpoint, status = 200) {
  const pending = page.waitForResponse(r => new URL(r.url()).pathname === endpoint && r.request().method() === 'POST');
  await button.click();
  const response = await pending;
  assert.equal(response.status(), status, await response.text());
  return response.json();
}
const inspect = () => postByClick(page.getByRole('button', { name: '조건 확인', exact: true }), '/api/summary-contract');
async function main() {
  browser = await chromium.launch({ headless: true, executablePath: process.env.CHROMIUM_PATH || 'C:/Users/Laptop_PC/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe' });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1100 }, locale: 'ko-KR', reducedMotion: 'reduce' });
  context.setDefaultTimeout(20000);
  await context.route('**/*', route => {
    const url = new URL(route.request().url());
    if (url.origin === BASE || ['data:', 'blob:'].includes(url.protocol)) return route.continue();
    external.push(url.origin + url.pathname); return route.abort();
  });
  page = await context.newPage();
  page.on('pageerror', e => errors.push(e.message));
  page.on('request', r => { if (r.method() === 'POST') requests.push(new URL(r.url()).pathname); });
  await step('01 demo health and oversized source preserved before session creation', async () => {
    assert.equal((await (await context.request.get(BASE + '/api/health')).json()).live, false);
    await page.goto(BASE);
    await page.getByRole('button', { name: '문서 요약 선택', exact: true }).click();
    await page.locator('.category-selection .selection-button').click();
    await page.locator('.task-input').fill('🙂'.repeat(12001));
    assert.equal(await page.locator('.task-input').inputValue(), '🙂'.repeat(12001));
    assert.equal(await page.getByRole('button', { name: '이 내용으로 시작', exact: true }).isDisabled(), true);
    assert.equal(requests.length, 0);
    await page.locator('.task-input').scrollIntoViewIfNeeded();
    await page.screenshot({ path: path.join(RUN, 'source-limit.png') });
  });
  await step('02 real summary comparison completes within eight choices', async () => {
    await page.locator('.task-input').fill('The launch moved to Friday. Testing remains unfinished.');
    let { session } = await postByClick(page.getByRole('button', { name: '이 내용으로 시작', exact: true }), '/api/sessions', 201);
    for (let n = 0; !session.done && n < 8; n++) {
      ({ session } = await postByClick(page.locator('.comparison-option').first(), `/api/sessions/${session.session_id}/choices`));
    }
    assert.equal(session.done, true); assert.ok(session.answered <= 8);
    await page.locator('.summary-contract').waitFor();
  });
  await step('03 too few sentences blocks output; explicit shortening preserves extraction', async () => {
    await page.getByLabel('요약 분량', { exact: true }).selectOption('long');
    await page.getByLabel('원문 표현 방식', { exact: true }).selectOption('fully');
    let contract = await inspect();
    assert.equal(contract.version, 2); assert.equal(contract.status, 'needs_resolution');
    assert.deepEqual(contract.available_resolutions, ['shorten', 'rephrase']);
    assert.equal(await page.locator('.summary-contract-result').count(), 0);
    await page.locator('.summary-contract-conflict').scrollIntoViewIfNeeded();
    await page.screenshot({ path: path.join(RUN, 'short-source-conflict.png') });
    await page.locator('input[value="shorten"]').check();
    contract = await inspect();
    assert.deepEqual(contract.effective_profile, { length: 'short', extractiveness: 'fully', topic: '' });
    assert.equal(contract.coverage_policy, 'all_required');
    assert.ok(!(contract.prompts.en.includes('The launch moved')));
    assert.ok(contract.task_requests.en.includes('The launch moved'));
  });
  await step('04 source edits invalidate output and three-passages conflict offers only applicable choices', async () => {
    await page.locator('.summary-contract-source').fill('The launch moved to Friday. Testing remains unfinished. Funding depends on approval.');
    assert.equal(await page.locator('.summary-contract-result').count(), 0);
    await page.getByLabel('요약 분량', { exact: true }).selectOption('short');
    await inspect();
    await page.locator('.summary-contract-sentences summary').click();
    for (const input of await page.locator('.summary-contract input[type="checkbox"]').all()) await input.check();
    let contract = await inspect();
    assert.equal(contract.status, 'needs_resolution');
    assert.deepEqual(contract.available_resolutions, ['expand', 'rephrase', 'keep_limits']);
    await page.locator('input[value="keep_limits"]').check();
    contract = await inspect();
    assert.equal(contract.coverage_policy, 'prioritize_with_omission');
    assert.match(await page.locator('.summary-contract-result').innerText(), /일부 생략 허용 · 전체 보존 아님/);
  });
  await step('05 no complete sentences offers no impossible shortening; focus boundary is consistent', async () => {
    await page.locator('.summary-contract-source').fill('Incomplete source without final punctuation');
    let contract = await inspect();
    assert.deepEqual(contract.available_resolutions, ['rephrase']);
    const topic = page.getByPlaceholder('예: 일정 변경과 남은 위험');
    await topic.fill('🙂'.repeat(300) + ' ');
    assert.equal(await page.getByRole('button', { name: '조건 확인', exact: true }).isDisabled(), true);
    assert.equal(await topic.inputValue(), '🙂'.repeat(300) + ' ');
    await topic.fill('🙂'.repeat(300));
    contract = await inspect();
    assert.equal(contract.status, 'needs_resolution');
    await topic.fill('');
  });
  await step('06 mobile contract choices fit viewport and preserve source', async () => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.locator('.summary-contract-source').fill('The launch moved to Friday. Testing remains unfinished.');
    await page.getByLabel('요약 분량', { exact: true }).selectOption('long');
    await inspect();
    const box = await page.locator('.summary-contract').boundingBox();
    assert.ok(box.x >= 0 && box.x + box.width <= 391);
    await page.locator('.summary-contract-conflict').scrollIntoViewIfNeeded();
    await page.screenshot({ path: path.join(RUN, 'mobile-conflict.png') });
    assert.equal(await page.locator('.summary-contract input[type="radio"]').count(), 2);
  });
  await step('07 AI answer settings and React style comparison remain separate and usable', async () => {
    await page.setViewportSize({ width: 1440, height: 1100 });
    await page.goto(BASE);
    await page.getByRole('button', { name: '코딩 도움 선택', exact: true }).click();
    await page.getByRole('button', { name: 'AI 답변 방식 설정', exact: true }).click();
    await page.getByRole('heading', { name: 'AI 답변 방식 설정', exact: true }).waitFor();
    await page.goto(BASE);
    await page.getByRole('button', { name: '코딩 도움 선택', exact: true }).click();
    await page.getByRole('button', { name: 'React 코드 스타일 비교', exact: true }).click();
    const { session } = await postByClick(page.getByRole('button', { name: '이 내용으로 시작', exact: true }), '/api/sessions', 201);
    assert.equal(session.domain_key, 'coding'); assert.equal(session.demo_mode, true);
    assert.equal(await page.locator('.comparison-option').count(), 2);
  });
  await step('08 no browser runtime errors or optimization/model requests', async () => {
    assert.deepEqual(errors, []);
    assert.ok(requests.every(p => p === '/api/summary-contract' || p === '/api/sessions' || /^\/api\/sessions\/[^/]+\/choices$/.test(p)));
  });
}
main().catch(e => { console.error(e.stack); process.exitCode = 1; }).finally(async () => {
  if (page && results.some(r => !r.pass)) await page.screenshot({ path: path.join(RUN, 'failure.png'), fullPage: true }).catch(() => {});
  fs.writeFileSync(path.join(RUN, 'results.json'), JSON.stringify({ results, errors, blocked_external: external, requests }, null, 2));
  await browser?.close();
});
