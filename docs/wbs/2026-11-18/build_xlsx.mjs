import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
const packages=process.env.CODEX_ARTIFACT_NODE_MODULES;
assert(packages,'Use the configured bundled runtime.');
const require=createRequire(path.join(packages,'..','artifact-loader.cjs'));
const {FileBlob,SpreadsheetFile}=await import(pathToFileURL(require.resolve('@oai/artifact-tool')).href);
const root=process.cwd(), qa=path.join(root,'tmp/final-20261118/wbs');
await fs.mkdir(qa,{recursive:true});
await fs.mkdir('outputs/wbs-20261118',{recursive:true});
const d=JSON.parse(await fs.readFile('docs/wbs/2026-11-18/wbs-v3.4.json','utf8'));
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load('outputs/wbs-20261112/Revealed_WBS_v3.3_보고서형.xlsx'));
const w=wb.worksheets.getItem('WBS'),g=wb.worksheets.getItem('간트차트'),u=wb.worksheets.getItem('UC 연결표');
console.log((await wb.inspect({kind:'sheet',include:'id,name',maxChars:1000})).ndjson);
const dates=JSON.stringify(w.getRange('G8:I28').values), formulas=JSON.stringify(w.getRange('G8:K28').formulas);
const gf=JSON.stringify(g.getRange('A8:R23').formulas);
w.getRange('A4').values=[['WBS v3.4 · 5단계 / 16개 주요 작업 · 상태·문서 2026-11-18 · 설계서 v1.3 · 코드 0bbff80']];
const rows=new Map();
for(let row=8;row<=28;row++) {
 const task=d.tasks.find(t=>t.id===w.getRange(`A${row}`).values[0][0]); if(!task) continue;
 rows.set(task.id,row);
 w.getRange(`K${row}`).values=[[task.status]];
 w.getRange(`M${row}`).values=[[task.note]];
}
w.getRange('A35').values=[['UC-02·03: 주 구현 3.1 / 관련 3.3 세션 접근·소유권·고정 TTL 구현 및 검증. UC-03은 3.2에서도 공통 사용.']];
w.getRange('A34').values=[['서식: 사용자 제공 중간보고서·기존 WBS / 최신 상태 근거: 11/17 검증과 11/18 설계서 v1.3 발행.']];
w.getRange('A38').values=[['기술 범위 완료와 공식 제출 완료는 다릅니다. 팀원 PC 리허설·수업 제출 요건 확인은 남아 있습니다. 계획일은 기존 일정 그대로입니다.']];
g.getRange('A4').values=[['파란 칸 = 계획 기간 · 상태·문서 2026-11-18 기준 · WBS의 날짜·상태 변경 시 함께 갱신']];
u.getRange('A4').values=[['설계서 v1.3 · 2026-11-18 · 주 구현과 공통 사용·세션 정책 연결 · 하위 UC는 부모 범위 상속']];
u.getRange('G7:G30').values=d.usecases.map(x=>[x.related_wbs.map(r=>`${r.id} (${r.role})`).join(' / ')||'-']);
u.getRange('A32').values=[['UC-02·03: 주 구현 3.1 / 관련 3.3 세션 정책 구현·검증. UC-03은 3.2에서도 공통 사용합니다.']];
u.getRange('A33').values=[['출처: docs/system-design/usecase-catalog.json · 설계서 v1.3 · 기술 검증 docs/verification/2026-11-17-readiness/']];
// Keep original typed dates/formulas and exercise editable dependencies before restoring inputs.
const row=rows.get('3.1'),gr=d.tasks.findIndex(t=>t.id==='3.1')+8;
const end=w.getRange(`H${row}`).values[0][0], state=w.getRange(`K${row}`).values[0][0];
w.getRange(`H${row}`).values=[[new Date('2026-11-20T00:00:00Z')]];
assert.equal(g.getRange(`M${gr}`).values[0][0],1);
w.getRange(`H${row}`).values=[[end]];
w.getRange(`K${row}`).values=[['보완중']];
assert.equal(w.getRange(`J${row}`).values[0][0],'');
assert.equal(g.getRange(`C${gr}`).values[0][0],'보완중');
w.getRange(`K${row}`).values=[[state]];
wb.recalculate();
assert.equal(JSON.stringify(w.getRange('G8:I28').values),dates);
assert.equal(JSON.stringify(w.getRange('G8:K28').formulas),formulas);
assert.equal(JSON.stringify(g.getRange('A8:R23').formulas),gf);
for(const t of d.tasks) {
 const r=rows.get(t.id),pct=w.getRange(`J${r}`).values[0][0];
 assert.equal(w.getRange(`K${r}`).values[0][0],t.status);
 assert.equal(pct,t.progress===null?'':t.progress);
}
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:20},maxChars:1800});
await fs.writeFile(path.join(qa,'checks.json'),JSON.stringify({datesPreserved:true,formulasPreserved:true,statusesVerified:16,editPropagationVerified:true,errorScan:errors.ndjson},null,2));
console.log(errors.ndjson);
await (await SpreadsheetFile.exportXlsx(wb)).save('outputs/wbs-20261118/Revealed_WBS_v3.4_보고서형.xlsx');
for(const [sheetName,range,file] of [['WBS','A4:M28','wbs.png'],['WBS','A32:M38','notes.png'],['간트차트','A7:R27','gantt.png'],['UC 연결표','A4:G33','links.png']]) {
 const image=await wb.render({sheetName,range,scale:1.2,format:'png'});
 await fs.writeFile(path.join(qa,file),new Uint8Array(await image.arrayBuffer()));
}
console.log('WBS v3.4 exported and all three sheets rendered.');
