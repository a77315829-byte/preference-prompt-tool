// Reusable live Artifact Session callback; no local deck or paid API calls.
const ROOT='C:/Users/Laptop_PC/preference-prompt-tool';
const REPO='https://github.com/a77315829-byte/preference-prompt-tool/blob/docs/wbs-v3.2/';
const EVIDENCE=REPO+'benchmarks/weekly_validation_2026_11_17/README.md';
export const slides=[
 {title:'목표: 확인한 요약 조건을 다음 작업에도 쓰기',rows:[['조건을 쉽게 표현','길이·표현 방식·남길 내용을 선택하고 확인합니다.'],['불가능한 조합을 먼저 확인','완전 발췌와 짧은 분량이 충돌하면 해결 방법을 고릅니다.'],['원문과 지침을 분리','확인한 지침을 저장하고 새 원문과 임시로 조합합니다.']],note:'40초. 사람의 편의성이나 시간 절감은 기대 가치이며 측정 결과로 말하지 않습니다. 출처: '+REPO+'CLAUDE.md'},
 {title:'선택에서 재사용까지 이어지는 제품 흐름',rows:[['01  원문과 원하는 조건','12,000자 상한 · 비교 최대 8회 · 미정 항목 확인'],['02  충돌 해결과 지침 확인','확대·축소·재서술·일부 생략 중 필요한 처리만 명시 선택'],['03  저장 → 새 작업','현재 언어의 지침만 보관 · 새 원문은 작업 요청에 조합']],note:'45초. 최대 8회는 충분성이 증명된 횟수가 아니라 부담 상한입니다. 새 원문의 내용 보존을 자동 보증하지 않습니다. 출처: '+REPO+'docs/verification/2026-11-17-readiness/DEMO.md'},
 {title:'충돌은 자동으로 숨기지 않고 선택하게 합니다',image:'01-summary-conflict.png',aside:'세 문장 모두 보존\n+ 1~2문장 완전 발췌\n\n처리를 고르기 전에는\n지침 출력을 차단\n\n분량 확대·재서술·\n일부 생략 중 선택',note:'50초. 합성 원문의 실제 무료 데모 화면입니다. 의미 압축의 가능성까지 판정한 결과는 아닙니다. 출처: '+REPO+'docs/verification/2026-11-17-readiness/results/01-summary-conflict.png'},
 {title:'재사용 지침에는 작업 원문을 넣지 않습니다',image:'03-new-task-reuse.png',aside:'확인한 지침만 저장\n\n새 원문과 임시 조합\n\n기존 지침·revision 유지\n\n새 원문에서 보존할\n내용은 다시 확인',note:'45초. 기본 비교 지침 저장과 조건 확인 결과 저장의 대상을 구분했습니다. 원문·선택 문장은 저장 본문에서 제외합니다. 출처: '+REPO+'docs/verification/2026-11-17-readiness/README.md'},
 {title:'코딩과 협업은 확장 기능으로 유지합니다',rows:[['AI 답변 방식 설정','설명 · 주석 · 구성 · 출력 — 네 항목'],['React 코드 스타일 비교','코드 구성 · 스타일 관리 · 타입 — 별도 세 축'],['팀 작업 연결','팀 기준 조합 · 출처 확인 · 인수인계 · 첨부 권한']],note:'35초. 회사의 기존 지침을 대체하거나 실제 팀 생산성 향상을 입증한 것은 아닙니다. 출처: '+REPO+'docs/system-design/chapters/02-usecases.md'},
 {title:'검증은 조건·내용·기능을 분리했습니다',rows:[['대조군을 강하게 설정','같은 원문·과제·확정 조건을 수동 지침과 제품에 제공'],['새 자료와 첫 응답 고정','미사용 MACSum 6원문 + 새 React 8과제 → 응답 28개'],['자동 검사와 독립 의미 검토','길이·타입·동작 검사 + 생성자가 아닌 익명 AI 검토 2명']],note:'55초. 과거 세 방식 실험은 별도 표본입니다. 일반 요청에 주지 않은 선호를 지시 위반으로 부르지 않습니다. 보조 에이전트는 실제 사용자 연구가 아닙니다. 출처: '+EVIDENCE},
 {title:'요약: 두 방식 모두 조건 충족, 내용은 17/18',table:[['지표','수동','제품'],['분량·표현 조건','6/6','6/6'],['핵심 사실·선택 정보','17/18','17/18'],['전체 보존 요청 사례','5/5','5/5']],foot:'같은 일부 생략 허용 사례에서 사실 1개 누락. 관측 동률이며 우위·통계적 동등성은 미입증.',note:'60초. 17/18을 100% 내용 보존으로 말하지 않습니다. 일부 생략을 허용한 지침과 전체 보존 의무를 구별했습니다. 출처: '+EVIDENCE},
 {title:'React: 타입·실제 동작·스타일을 따로 확인',table:[['지표','수동','제품'],['strict 타입 검사','8/8','8/8'],['React/JSDOM 개별 동작','40/40','40/40'],['세 스타일 축 동시 일치','8/8','8/8']],foot:'새 합성 과제 8개, 현재 v2 영어 지침. 코드 설명의 일본어 한 단어 혼입도 별도 기록.',note:'45초. 한·영 지침의 의미 정렬과 한국어 출력 실험은 다릅니다. 이번 출력 비교는 영어 지침을 썼습니다. 타입·동작 통과가 모든 설명 품질을 보증하지 않습니다. 출처: '+EVIDENCE},
 {title:'저장·권한·복구까지 확인한 기술 범위',table:[['검사','결과','범위'],['로컬 Python','1440 통과','1 Windows skip · API 16 제외'],['프론트','137 통과','빌드 성공'],['실제 HTTP / UI','10 / 6 항목 통과','합성 자료 · 로컬 앱'],['GitHub / Container','기준 커밋 성공','CI skip 3개는 로컬 3/3 확인']],foot:'수치는 코드 0bbff80의 근거입니다. 팀원 PC 리허설과 광범위한 보안 감사는 별도입니다.',note:'50초. 스냅샷 단위 검사 7개는 1440에 포함됩니다. CI의 자료 부족 3개와 Windows skip 1개는 다른 검사입니다. 출처: '+REPO+'docs/verification/2026-11-17-readiness/README.md'},
 {title:'GEPA는 필수화할 근거가 아직 없습니다',rows:[['실제 탐색기를 오프라인으로 실행','개선 6 · 후보 선택 6 · 최종 평가 9원문을 분리'],['선택 결과는 현재 지침 유지','두 성찰 후보가 선택 점수를 개선하지 못함'],['다음 조건','새 원문의 안정된 이득과 비용·대기시간을 함께 확인']],note:'45초. 운영 점수와 연구용 내용 보존 평가는 다릅니다. 유료 모델 API 없이 Codex 응답을 연결한 연구이지 무제한 무료 운영의 증거가 아닙니다. 출처: '+REPO+'benchmarks/summary_gepa_offline/README.md'},
 {title:'남은 일은 사람의 확인과 제출 확정입니다',rows:[['팀원 PC에서 시연','설치 → 충돌 확인 → 저장 → 새 작업 → 로그아웃'],['공식 제출 조건 확인','지정 양식 · 발표 시간 · 제출 채널 · 마감'],['최종 인계','자료 검토 · 버전 합의 · 실행·복구 안내 전달']],note:'45초. 자동 시연과 문서 준비를 팀 참석 리허설로 표시하지 않습니다. WBS의 기존 계획일은 유지했고 진행률을 임의 산정하지 않았습니다. 출처: '+REPO+'docs/wbs/2026-11-18/README.md'},
 {title:'이번 결과의 의미와 다음 판단',rows:[['확보한 것','명시 조건의 전달 · 새 자료에서의 출력 검사 · 저장·재사용 흐름'],['주장하지 않는 것','수동보다 우수함 · 사람 시간 절감 · 숨은 취향의 정확한 추정'],['발전 방향','실패 근거로 조건·평가 계약을 고치고, 편의 가치는 사람 연구로 확인']],note:'40초. 12개 본문 슬라이드와 표지를 약 9~10분으로 설명합니다. 실제 발표 시간에 맞춰 팀 리허설에서 조정합니다. 출처: '+REPO+'docs/final/2026-11-18/report.md'},
 {title:'질문 대비: 수동과 같으면 왜 쓰나요?',rows:[['수동 프롬프트도 잘 동작했습니다','제품의 근거를 품질 우위로 과장하지 않습니다.'],['제공하는 것은 반복 가능한 작업 흐름입니다','조건 선택·충돌 확인·지침 보관·새 작업 조합을 제공합니다.'],['채택할 만큼 편한지는 아직 모릅니다','실제 사용자 과제에서 설정·수정 시간과 선호를 분리 측정해야 합니다.']],note:'보충 1. 공식 평가 질문에 대비한 답변. 현재 결과와 기대 효과를 구분합니다.'},
 {title:'질문 대비: 8회·MACSum·무료 검증의 의미',table:[['질문','답변'],['8회면 선호를 알 수 있나요?','상한일 뿐, 정확도 보장이 아닙니다.'],['MACSum으로 개인화를 증명했나요?','영어 원문·조건 평가 맥락으로 사용했습니다.'],['완전히 무료 운영인가요?','이번 유료 API는 0회, Codex 사용량은 소비합니다.'],['사람 없이도 무엇을 말할 수 있나요?','명시 조건 전달과 정의된 기술 검사 범위입니다.']],note:'보충 2. 실사용 효과와 기술 검증 범위를 분리한 답변. 출처: '+REPO+'CLAUDE.md'},
 {title:'전체 설계와 근거를 함께 전달합니다',rows:[['전체 분석·설계서 v1.3','docs/system-design/ — 24 상위 UC · 79 하위 UC · 77개 그림'],['WBS v3.4와 최종 보고 준비본','docs/wbs/2026-11-18/ · docs/final/2026-11-18/'],['실험·운영 원자료','benchmarks/weekly_validation_2026_11_17/\ndocs/verification/2026-11-17-readiness/']],note:'보충 3. 저장소 https://github.com/a77315829-byte/preference-prompt-tool · PR #14. 문서 게시 브랜치 docs/wbs-v3.2와 산출물 판본 v3.4는 다릅니다.'},
];

export default async function build({presentation,input}) {
 const text=(s,content,left,top,width,height,size=26,bold=false,color='#20314C')=>{
  const x=s.shapes.add({geometry:'textbox',position:{left,top,width,height},fill:'none',line:{fill:'none',width:0}});
  x.text=content;x.text.style={typeface:'Malgun Gothic',fontSize:size,bold,color};return x;
 };
 if(input.init) {
  presentation.slides.keep([1]);
  presentation.resolve('sh/7ap0fy94').text.style={typeface:'Malgun Gothic',fontSize:48,bold:true,color:'#20314C'};
  presentation.resolve('sh/69gzmt8j').text.style={typeface:'Malgun Gothic',fontSize:24,color:'#556579'};
  presentation.slides.getItem(0).speakerNotes.text='20초. 요약 조건을 재사용 지침으로 만들고 그 전달 결과를 검증한 프로젝트입니다. 최종발표 준비본이며 팀 리허설과 제출 요건 확인이 남아 있습니다.';
 }
 for(let i=input.start;i<input.end;i++) {
  const d=slides[i],s=presentation.slides.add({width:1280,height:720});s.background.fill='#FFFFFF';
  text(s,d.title,66,55,1150,85,38,true);
  if(d.rows) d.rows.forEach((r,j)=>{const y=185+j*138;text(s,r[0],70,y,1110,44,29,true);text(s,r[1],70,y+51,1110,74,24,false,'#556579');});
  if(d.image) {s.images.add({path:ROOT+'/docs/verification/2026-11-17-readiness/results/'+d.image,fit:'contain',position:{left:56,top:150,width:800,height:540}});text(s,d.aside,900,185,320,460,25,false,'#40548A');}
  if(d.table) {
   const cols=d.table[0].length,table=s.tables.add({rows:d.table.length,columns:cols,left:70,top:180,width:1140,height:d.table.length*75,columnWidths:cols===3?[570,285,285]:[390,750],values:d.table});
   for(let r=0;r<d.table.length;r++)for(let c=0;c<cols;c++){let cell=table.getCell(r,c);cell.fill=r===0?'#E9EDF8':r%2?'#F7F9FC':'#FFFFFF';cell.text.style={typeface:'Malgun Gothic',fontSize:cols===3&&i===8?23:25,bold:r===0,color:'#20314C'};}
   if(d.foot)text(s,d.foot,72,595,1130,80,21,false,'#556579');
  }
  text(s,String(i+2),1190,680,40,24,16,false,'#7A8799');s.speakerNotes.text=d.note;
 }
 return {slides:presentation.slides.items.length,added:[input.start,input.end]};
}
