import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';

const packages=process.env.CODEX_ARTIFACT_NODE_MODULES;
assert(packages,'Set CODEX_ARTIFACT_NODE_MODULES to the bundled node_modules directory.');
const runtimeRequire=createRequire(path.join(packages,'..','artifact-loader.cjs'));
const {FileBlob,SpreadsheetFile}=await import(pathToFileURL(runtimeRequire.resolve('@oai/artifact-tool')).href);
const root=process.cwd(), qa=path.join(root,'tmp/wbs-20261112');
const d=JSON.parse(await fs.readFile(path.join(root,'docs/wbs/2026-11-12/wbs-v3.3.json'),'utf8'));
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(root,'outputs/wbs-20261112/Revealed_WBS_v3.2_보고서형.xlsx')));
const w=wb.worksheets.getItem('WBS'), g=wb.worksheets.getItem('간트차트'), links=wb.worksheets.getItem('UC 연결표');
wb.recalculate();
const formulas=JSON.stringify(w.getRange('G8:K28').formulas), ganttFormulas=JSON.stringify(g.getRange('A8:R23').formulas);
const inputs=w.getRange('G8:K28').values;
w.getRange('A4').values=[['WBS v3.3 · 5단계 / 16개 주요 작업 · 제품 상태 11/12 / 문서 반영·UC 연결 11/13 기준 · 설계서 v1.2']];
w.getRange('L7').values=[['저장소 최초 추가일']];
w.getRange('M7').values=[['비고(반영·남은 일)']];
w.getRange('L7:M7').format.wrapText=true;
const taskRows=new Map();
for(let row=8;row<=28;row++){
 const id=w.getRange(`A${row}`).values[0][0], t=d.tasks.find(t=>t.id===id);
 if(!t) continue;
 taskRows.set(id,row);
 w.getRange(`E${row}`).values=[[t.uc_scope]];
 w.getRange(`M${row}`).values=[[t.note||'-']];
}
const sessionRow=taskRows.get('3.3');
w.getRange(`A${sessionRow}:M${sessionRow}`).format.rowHeight=54;
w.getRange(`E${sessionRow}`).format.wrapText=true;
w.getRange('M8:M28').format.wrapText=true;
w.getRange('A35').values=[['UC 연결: 주 구현은 유지하며 UC-03의 3.2 공통 사용, UC-02·03의 3.3 세션 정책 보완 예정을 구분합니다.']];
w.getRange('A37').values=[['저장소 최초 추가일은 해당 경로의 최초 추가 커밋 작성일입니다. GitHub 업로드 시점이나 실제 작업 시작·완료일을 뜻하지 않습니다.']];
w.getRange('A38').values=[['요약 v2 문서 반영은 완료됐습니다. 세션 정책 확정 후 설계 반영과 새 출력 검증은 남아 있으며 3.3의 계정 격리는 보완 예정입니다.']];
g.getRange('A27').values=[['경로의 최초 추가 커밋 작성일은 WBS 시트와 PDF 간트의 표식에 있습니다. 업로드 시점이나 실제 작업 시작·완료일은 아닙니다.']];
links.getRange('D6').values=[['주 구현 WBS']];
links.getRange('D6').format.wrapText=true;
links.getRange('G6:G30').copyFrom(links.getRange('F6:F30'),'all');
links.getRange('G6').values=[['관련 WBS']];
links.getRange('G7:G30').values=d.usecases.map(u=>[u.related_wbs.map(x=>`${x.id} (${x.role})`).join(' / ')||'-']);
links.getRange('G1:G35').format.columnWidthPx=260;
links.getRange('G6:G30').format.wrapText=true;
links.getRange('A4').values=[['설계서 v1.2 · 주 구현과 공통 사용·보완 예정 연결을 구분 · 하위 UC는 부모의 연결 범위를 상속']];
links.getRange('A32').values=[['UC-02·03: 주 구현 3.1 / 관련 3.3 세션 접근·소유권·만료 정책 보완 예정. UC-03은 3.2에서도 공통 사용합니다.']];
links.getRange('A33').values=[['출처: usecase-catalog.json · 전체 분석·설계서 v1.2 / 2026-11-13 · 예정 연결은 현재 계정 격리 완료를 뜻하지 않습니다.']];

// Verify that editable dates and statuses still drive dependent formulas; restore every temporary edit.
const r=taskRows.get('3.1'), gr=d.tasks.findIndex(t=>t.id==='3.1')+8;
const oldEnd=w.getRange(`H${r}`).values[0][0];
w.getRange(`H${r}`).values=[[new Date('2026-11-20T00:00:00Z')]];
assert.equal(g.getRange(`M${gr}`).values[0][0],1);
w.getRange(`H${r}`).values=[[oldEnd]];
w.getRange(`K${r}`).values=[['보완중']];
assert.equal(w.getRange(`J${r}`).values[0][0],'');
assert.equal(g.getRange(`C${gr}`).values[0][0],'보완중');
w.getRange(`K${r}`).values=[['완료']];
wb.recalculate();
assert.deepEqual(w.getRange('G8:K28').values,inputs);
assert.equal(JSON.stringify(w.getRange('G8:K28').formulas),formulas);
assert.equal(JSON.stringify(g.getRange('A8:R23').formulas),ganttFormulas);
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:20},maxChars:1600});
console.log(errors.ndjson);
await fs.mkdir(qa,{recursive:true});
await fs.writeFile(path.join(qa,'v3.3-workbook-check.json'),JSON.stringify({inputEditsRecalculated:true,inputsRestored:true,formulasPreserved:true,errorScan:errors.ndjson},null,2));
await (await SpreadsheetFile.exportXlsx(wb)).save(path.join(root,'outputs/wbs-20261112/Revealed_WBS_v3.3_보고서형.xlsx'));
for(const [sheetName,range,file] of [['WBS','A4:M28','v3.3-wbs.png'],['WBS','A32:M38','v3.3-notes.png'],['간트차트','A7:R27','v3.3-gantt.png'],['UC 연결표','A4:G33','v3.3-links.png']]){
 const blob=await wb.render({sheetName,range,scale:1.2,format:'png'});
 await fs.writeFile(path.join(qa,file),new Uint8Array(await blob.arrayBuffer()));
}
console.log('Exported v3.3; preserved and recalculated dates/status/formulas; rendered all three sheets.');
