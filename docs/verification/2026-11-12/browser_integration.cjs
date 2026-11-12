// Real Chromium + production build + real local HTTP + isolated cookie contexts.
// Only synthetic data. No model endpoints or external network destinations.
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const {chromium} = require('C:/Program Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1110-778-0_26.1110.778.0_x64__3k8sg7r9htsxt/dependencies/node/node_modules/playwright');
const ROOT = path.resolve(__dirname, '../../..');
const BASE = 'http://127.0.0.1:18762';
const RUN = path.join(ROOT, 'tmp/integration-20261112', process.argv[2] || 'browser-run1');
fs.mkdirSync(RUN, {recursive:true});
const results = [], requests = [], pageErrors = [], blockedExternal = [];
let browser, a, b, c, anonymous, pa, pb, stale, item, privateId, privateRevision, sharedId, sharedRevision, pref;
const suffix = crypto.randomBytes(4).toString('hex');
const owner = `audit_a_${suffix}`, recipient = `audit_b_${suffix}`, replacement = `audit_c_${suffix}`;
const password = `Local-test-only-${suffix}!`;
const sharedBytes = Buffer.from('팀원에게 전달할 합성 자료입니다. 실제 사용자 자료가 아닙니다.\n');
const profile = {language:'TypeScript',framework:'React',extra:'',preferences:{explanation:'brief',comments:'essential',structure:'compact',output:'complete'}};
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const fileRow = (page,name) => page.locator('.handoff-attachments li').filter({hasText:name});

async function api(context, endpoint, body, status=200, headers={}) {
  const response = await context.request.fetch(BASE+endpoint, {
    method:body===undefined?'GET':'POST', data:body, headers, timeout:15000,
  });
  const raw=await response.body();
  requests.push({endpoint,method:body===undefined?'GET':'POST',status:response.status()});
  assert.equal(response.status(),status,`${endpoint}: ${raw.toString().slice(0,180)}`);
  const text=raw.toString('utf8');
  return response.headers()['content-type']?.includes('json') ? JSON.parse(text) : raw;
}
const get = async () => (await api(a,`/api/handoffs/${item.id}`)).handoff;
async function postUI(page, button, endpoint, expected=200) {
  const responsePromise=page.waitForResponse(r=>new URL(r.url()).pathname===endpoint && r.request().method()==='POST');
  await page.getByRole('button',{name:button,exact:true}).click();
  const response=await responsePromise;
  assert.equal(response.status(),expected,`${endpoint}: ${await response.text()}`);
  const payload=await response.json();
  await page.waitForFunction(()=>![...document.querySelectorAll('.handoffs-section button')].some(el=>el.textContent==='처리하는 중…'));
  return payload;
}
async function openItem(page) {
  await page.goto(`${BASE}/?handoff=${item.id}`);
  await page.locator('#handoff-title').waitFor();
  await page.waitForFunction(()=>document.querySelector('#handoff-title')?.value);
}
async function attach(name, bytes) {
  await pa.locator('#handoff-file').setInputFiles({name,mimeType:'text/plain',buffer:bytes});
  item=(await postUI(pa,'첨부 파일 저장',`/api/handoffs/${item.id}/attach`)).handoff;
  await fileRow(pa,name).locator('a[download]').waitFor();
  return item.body.attachments.at(-1).id;
}
async function share(username) {
  await pa.locator('#handoff-recipient').fill(username);
  item=(await postUI(pa,'이 팀원에게 공유',`/api/handoffs/${item.id}/share`)).handoff;
}
async function signup(page, username) {
  await page.goto(`${BASE}/?handoff=${'0'.repeat(32)}`);
  await page.getByRole('button',{name:'계정 만들기',exact:true}).click();
  await page.locator('#auth-username').fill(username);
  await page.locator('#auth-password').fill(password);
  await page.locator('#auth-confirm').fill(password);
  await page.getByRole('button',{name:'가입하고 시작',exact:true}).click();
  await page.getByRole('button',{name:'새 작업 넘기기',exact:true}).waitFor();
}
async function step(name, fn) {
  const start=Date.now();
  try {await fn(); results.push({name,pass:true,ms:Date.now()-start}); console.log(`PASS ${name}`);}
  catch(e){results.push({name,pass:false,ms:Date.now()-start,error:e.message});throw e;}
}
async function context() {
  const ctx=await browser.newContext({viewport:{width:1440,height:1100},locale:'ko-KR',acceptDownloads:true});
  ctx.setDefaultTimeout(15000);
  await ctx.route('**/*',route=>{
    const url=new URL(route.request().url());
    if (url.origin===BASE || ['data:','blob:'].includes(url.protocol)) return route.continue();
    blockedExternal.push(url.origin+url.pathname);return route.abort();
  });
  ctx.on('page',p=>{p.on('pageerror',e=>pageErrors.push(e.message));p.on('dialog',d=>d.accept());});
  return ctx;
}

async function main() {
  browser=await chromium.launch({headless:true,executablePath:'C:/Users/Laptop_PC/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe'});
  a=await context();b=await context();c=await context();anonymous=await context();
  pa=await a.newPage();pb=await b.newPage();
  await step('01 offline health and two independent browser signups',async()=>{
    const health=await api(anonymous,'/api/health');assert.equal(health.live,false);
    await signup(pa,owner);await signup(pb,recipient);
    await api(c,'/api/auth/signup',{username:replacement,password});
    const au=(await api(a,'/api/auth/me')).user,bu=(await api(b,'/api/auth/me')).user;
    assert.notEqual(au.id,bu.id);assert.equal(au.username,owner);assert.equal(bu.username,recipient);
  });
  await step('02 private source preference preserved separately',async()=>{
    pref=(await api(a,'/api/preferences',{title:'원본 보존 대조',domainKey:'coding',prompt:'원본 지침: 검증한 내용만 말한다.',note:'합성 검사 자료'},201)).preference;
    await api(b,`/api/preferences/${pref.id}`,undefined,404);
  });
  await step('03 owner creates handoff through UI',async()=>{
    await pa.getByRole('button',{name:'새 작업 넘기기',exact:true}).click();
    for(const [key,value] of Object.entries({title:'두 계정 통합 검증',purpose:'공유 권한과 자료 보존 확인',progress:'작성자 최초 기록',remaining:'팀원이 확인하고 이어받기',prompt:pref.prompt,references:'src/App.jsx'})) await pa.locator(`#handoff-${key}`).fill(value);
    item=(await postUI(pa,'내 작업으로 저장','/api/handoffs',201)).handoff;
    assert.equal(item.revision,1);assert.equal(item.status,'draft');
  });
  await step('04 draft denied to recipient, third account and anonymous',async()=>{
    await api(b,`/api/handoffs/${item.id}`,undefined,404);
    await api(c,`/api/handoffs/${item.id}/history`,undefined,404);
    await api(anonymous,`/api/handoffs/${item.id}`,undefined,401);
    await pb.goto(`${BASE}/?handoff=${item.id}`);
    await pb.getByRole('alert').waitFor();assert.equal(await pb.locator('#handoff-title').count(),0);
  });
  await step('05 attach then remove private draft file through UI',async()=>{
    privateId=await attach('공유 전 비공개.txt',Buffer.from('PRIVATE synthetic note'));
    privateRevision=item.revision;
    const response=pa.waitForResponse(r=>r.url().includes(`/${item.id}/detach`));
    await fileRow(pa,'공유 전 비공개.txt').getByRole('button',{name:/^현재 첨부에서 빼기/}).click();
    assert.equal((await response).status(),200);item=await get();assert.equal(item.body.attachments.length,0);
  });
  await step('06 attach shared UTF-8 file and share to second account through UI',async()=>{
    sharedId=await attach('팀 전달 자료.txt',sharedBytes);await share(recipient);sharedRevision=item.revision;
    assert.equal(item.recipient,recipient);assert.equal(item.status,'shared');
    await openItem(pb);assert.equal(await pb.locator('#handoff-purpose').inputValue(),item.body.purpose);
    assert.equal(await pb.locator('#handoff-progress').getAttribute('readonly'),'');
    await pb.screenshot({path:path.join(RUN,'recipient-shared.png'),fullPage:true});
  });
  await step('07 recipient downloads exact bytes and opens safe preview in real tab',async()=>{
    const downloadPromise=pb.waitForEvent('download');
    await fileRow(pb,'팀 전달 자료.txt').locator('a[download]').click();
    const download=await downloadPromise;const dest=path.join(RUN,'downloaded.txt');await download.saveAs(dest);
    assert.deepEqual(fs.readFileSync(dest),sharedBytes);
    const popupPromise=pb.waitForEvent('popup');await fileRow(pb,'팀 전달 자료.txt').getByRole('link',{name:/^열기/}).click();
    const popup=await popupPromise;await popup.waitForLoadState();assert.equal((await popup.locator('body').innerText()).trim(),sharedBytes.toString().trim());await popup.close();
  });
  await step('08 private history/files, unauthorized files and pre-claim editing denied',async()=>{
    await api(b,`/api/handoffs/${item.id}/history/${privateRevision}`,undefined,404);
    for(const rev of [privateRevision,sharedRevision]) await api(b,`/api/handoffs/${item.id}/files/${privateId}?revision=${rev}`,undefined,404);
    await api(anonymous,`/api/handoffs/${item.id}/files/${sharedId}?revision=${sharedRevision}`,undefined,401);
    await api(c,`/api/handoffs/${item.id}/files/${sharedId}?revision=${sharedRevision}`,undefined,404);
    await api(b,`/api/handoffs/${item.id}/update`,{...item.body,title:item.title,revision:item.revision,progress:'FORBIDDEN'},403);
    await api(a,`/api/handoffs/${item.id}/update`,{...item.body,title:item.title,revision:item.revision},403,{Origin:'https://example.invalid'});
  });
  await step('09 recipient replacement revokes body, history and file access',async()=>{
    await share(replacement);
    for(const endpoint of [`/api/handoffs/${item.id}`,`/api/handoffs/${item.id}/history`,`/api/handoffs/${item.id}/files/${sharedId}?revision=${sharedRevision}`]) await api(b,endpoint,undefined,404);
    const current=(await api(c,`/api/handoffs/${item.id}`)).handoff;assert.equal(current.recipient,replacement);
    await api(c,`/api/handoffs/${item.id}/history/${sharedRevision}`,undefined,404);
  });
  await step('10 denied reopen clears revoked content in already-open browser',async()=>{
    await pb.getByRole('button',{name:'작업 열기',exact:true}).click();
    await pb.getByRole('alert').waitFor();
    assert.equal(await pb.locator('#handoff-title').count(),0,'Revoked handoff must disappear after server rejects reopening it');
    await pb.screenshot({path:path.join(RUN,'revoked-denied.png'),fullPage:true});
  });
  await step('11 reshare restores current access without old private history',async()=>{
    await share(recipient);sharedRevision=item.revision;await openItem(pb);
    await api(b,`/api/handoffs/${item.id}/history/${sharedRevision-1}`,undefined,404);
    assert.deepEqual(await api(b,`/api/handoffs/${item.id}/files/${sharedId}?revision=${sharedRevision}`),sharedBytes);
  });
  await step('12 concurrent owner tabs preserve rejected draft and current server version',async()=>{
    stale=await a.newPage();await openItem(stale);
    await pa.locator('#handoff-progress').fill('최신 작성자 변경');item=(await postUI(pa,'변경 내용 저장',`/api/handoffs/${item.id}/update`)).handoff;
    await stale.locator('#handoff-progress').fill('오래된 창의 보존할 초안');
    await postUI(stale,'변경 내용 저장',`/api/handoffs/${item.id}/update`,409);
    await stale.getByRole('alert').waitFor();assert.equal(await stale.locator('#handoff-progress').inputValue(),'오래된 창의 보존할 초안');
    assert.equal((await get()).body.progress,'최신 작성자 변경');
    await stale.screenshot({path:path.join(RUN,'version-conflict.png'),fullPage:true});await stale.close();stale=null;
  });
  await step('13 recipient claims and edits; author becomes read-only',async()=>{
    await openItem(pb);item=(await postUI(pb,'이어서 맡기',`/api/handoffs/${item.id}/claim`)).handoff;
    await pb.locator('#handoff-progress').fill('받은 팀원이 이어서 수정');item=(await postUI(pb,'변경 내용 저장',`/api/handoffs/${item.id}/update`)).handoff;
    await openItem(pa);assert.equal(await pa.locator('#handoff-progress').getAttribute('readonly'),'');
    await api(a,`/api/handoffs/${item.id}/update`,{...item.body,title:item.title,revision:item.revision},403);
    assert.equal((await get()).body.progress,'받은 팀원이 이어서 수정');
  });
  await step('14 detached file denied in current version but retained in authorized history',async()=>{
    const response=pb.waitForResponse(r=>r.url().includes(`/${item.id}/detach`));
    await fileRow(pb,'팀 전달 자료.txt').getByRole('button',{name:/^현재 첨부에서 빼기/}).click();
    item=(await (await response).json()).handoff;
    await api(b,`/api/handoffs/${item.id}/files/${sharedId}?revision=${item.revision}`,undefined,404);
    assert.deepEqual(await api(b,`/api/handoffs/${item.id}/files/${sharedId}?revision=${sharedRevision}`),sharedBytes);
    assert.equal((await api(a,`/api/preferences/${pref.id}`)).preference.prompt,pref.prompt);
  });
  await step('15 completion/reopening and history through recipient UI',async()=>{
    item=(await postUI(pb,'작업 완료로 표시',`/api/handoffs/${item.id}/complete`)).handoff;assert.equal(item.status,'done');
    await api(b,`/api/handoffs/${item.id}/update`,{...item.body,title:item.title,revision:item.revision},403);
    item=(await postUI(pb,'다시 진행하기',`/api/handoffs/${item.id}/reopen`)).handoff;assert.equal(item.status,'active');
    await pb.getByRole('button',{name:'이전 기록 확인',exact:true}).click();await pb.getByRole('button',{name:`${sharedRevision}번째 기록 보기`,exact:true}).click();
    await pb.getByRole('button',{name:'현재 작업으로 돌아가기',exact:true}).waitFor();
    assert.equal(await pb.locator('#handoff-progress').getAttribute('readonly'),'');
    await pb.screenshot({path:path.join(RUN,'history-view.png'),fullPage:true});
    await pb.getByRole('button',{name:'현재 작업으로 돌아가기',exact:true}).click();
  });
  await step('16 logout clears draft and API access; relogin restores saved version',async()=>{
    await pb.locator('#handoff-remaining').fill('로그아웃 때 버릴 합성 초안');
    await pb.getByRole('button',{name:'로그아웃',exact:true}).click();
    await pb.goto(`${BASE}/?handoff=${item.id}`);
    await pb.locator('#auth-username').waitFor();
    await api(b,`/api/handoffs/${item.id}`,undefined,401);
    assert.equal(await pb.evaluate(()=>Object.values(sessionStorage).some(v=>v.includes('로그아웃 때 버릴 합성 초안'))),false);
    await pb.locator('#auth-username').fill(recipient);await pb.locator('#auth-password').fill(password);
    await pb.locator('.auth-form').getByRole('button',{name:'로그인',exact:true}).click();
    await pb.getByRole('button',{name:'새 작업 넘기기',exact:true}).waitFor();await openItem(pb);
    assert.notEqual(await pb.locator('#handoff-remaining').inputValue(),'로그아웃 때 버릴 합성 초안');
  });
  await step('17 no uncaught browser errors and source preference unchanged',async()=>{
    assert.deepEqual(pageErrors,[]);assert.deepEqual(blockedExternal,[]);
    assert.equal((await api(a,`/api/preferences/${pref.id}`)).preference.prompt,pref.prompt);
  });
  await step('18 team privacy, invitation control and membership over real HTTP',async()=>{
    const team=(await api(a,'/api/coding-work/teams',{name:'통합 검증 전용 비공개 팀',profile,rules:['기존 테스트 유지']},201)).team;
    const code=team.code;
    await api(b,`/api/coding-work/teams/${code}`,undefined,403);
    const hidden=(await api(c,`/api/teams/${code}`)).team;
    assert.equal(hidden.requires_join,true);assert.notEqual(hidden.name,team.name);
    await api(anonymous,`/api/coding-work/teams/${code}`,undefined,401);
    await api(a,`/api/teams/${code}/invitation`,{enabled:false});
    await api(b,`/api/coding-work/teams/${code}/join`,{},403);
    await api(a,`/api/teams/${code}/invitation`,{enabled:true});
    await api(b,`/api/coding-work/teams/${code}/join`,{});
    await api(b,`/api/teams/${code}/invitation`,{enabled:false},400);
    await api(a,`/api/teams/${code}/invitation`,{enabled:false});
    await api(c,`/api/coding-work/teams/${code}/join`,{},403);
    assert.equal((await api(b,`/api/coding-work/teams/${code}`)).team.name,team.name);
    const source={profile,teamSelection:{code,revision:team.revision,choices:{}}};
    const draft=(await api(b,'/api/coding-work/resolve',source)).draft;
    await api(b,'/api/coding-work/save',{...source,title:'조합 충돌',snapshot:'stale'},409);
    const saved=(await api(b,'/api/coding-work/save',{...source,title:'조합한 새 지침',snapshot:draft.snapshot},201)).preference;
    assert.equal(saved.coding_team_context.code,code);
    await api(a,`/api/preferences/${saved.id}`,undefined,404);
    const next=(await api(a,`/api/coding-work/teams/${code}/update`,{profile,rules:['새 기준'],revision:team.revision})).team;
    await api(a,`/api/coding-work/teams/${code}/update`,{profile,rules:['오래된 기준'],revision:team.revision},409);
    const reloaded=(await api(b,`/api/preferences/${saved.id}`)).preference;
    assert.equal(reloaded.prompt,saved.prompt);assert.equal(reloaded.coding_team_context.revision,team.revision);
    assert.equal((await api(b,`/api/coding-work/teams/${code}`)).team.revision,next.revision);
    assert.equal((await api(a,`/api/preferences/${pref.id}`)).preference.prompt,pref.prompt);
  });
}

(async()=>{
  let failed;
  try{await main();}catch(e){failed=e;console.error(e.stack);}
  finally{
    if(failed) for(const [label,page] of [['owner',pa],['recipient',pb]]) if(page&&!page.isClosed()){
      await page.screenshot({path:path.join(RUN,`${label}-failure.png`),fullPage:true}).catch(()=>{});
      fs.writeFileSync(path.join(RUN,`${label}-failure.txt`),await page.locator('body').innerText().catch(()=>''));
    }
    fs.writeFileSync(path.join(RUN,'result.json'),JSON.stringify({pass:!failed,results,requests,pageErrors,blockedExternal,
      browser:browser?.version(),contexts:'two active browser accounts plus replacement account and anonymous control',
      paidModelApiCalls:0,completedAt:new Date().toISOString()},null,2));
    await browser?.close();
  }
  if(failed)process.exitCode=1;
})();
