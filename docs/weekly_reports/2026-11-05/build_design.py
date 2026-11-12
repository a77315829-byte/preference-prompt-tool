"""Course design record. Reads source literals only; never opens the user database."""
from pathlib import Path
import ast
import sqlite3

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
OUT = HERE / 'Revealed_설계문서_2026-11-05.md'
HEAD = 'a2f12928717c11555c7376d0efdd27e0b0703b51'
REPO = 'https://github.com/a77315829-byte/preference-prompt-tool'

# id, phase, deliverable, responsibility, evidence, actual cells, planned cells
WBS = [
 ('1.1','분석','기존 연구·서비스 범위 정리','공동','11/05 대조',[0],[]),
 ('2.1','설계','기능·비기능 요구사항 / WBS','윤정우','11/05 문서화',[0],[1]),
 ('2.2','설계','UML·ERD·테이블·API 명세','윤정우','11/05 문서화',[0],[1]),
 ('2.3','설계','화면 정의·와이어프레임·스토리보드','윤정우','11/05 문서화',[0],[1]),
 ('3.1','구현','환경·예시 선택 / 지침 생성','윤정우','11/03~04 구현',[0],[1]),
 ('3.2','구현','보관·재사용·팀 조합·출처 이력','윤정우','11/03 구현',[0],[1,2]),
 ('3.3','구현','인수인계·첨부·접근 권한','윤정우','11/03~04 구현',[0],[2]),
 ('3.4','구현','업무 템플릿·요청 점검·GEPA 연결','윤정우','11/03~04 구현',[0],[2]),
 ('3.5','연구','React 비교 실험 / 평가 도구','고차원','11/04 결과',[0],[1,2]),
 ('4.1','통합','연구 변경 선별 / 오류 수정','공동','미통합',[],[1,2]),
 ('4.2','검증','초안·작업 복귀 / 회귀 검사','윤정우','문제 재현',[0],[1,2]),
 ('4.3','검증','독립 과제의 스타일·기능 평가','고차원','후속 계획',[],[1,2,3]),
 ('5.1','이행','웹 호스팅 준비 / 운영 확인','윤정우','11/04 로컬 준비',[0],[3,4]),
 ('5.2','안정화','최종 시연·문서·결과 정리','공동','후속 계획',[],[4,5]),
]
FR = [
 ('FR01','계정·권한','로그인 계정별 보관함·작업을 구분한다.','구현','auth.py / api_server.py'),
 ('FR02','기존 선택 비교','요약·React 결과를 비교해 지침을 만든다.','기존 유지','service.py / engine/'),
 ('FR03','코딩 선호','환경과 설명·주석·구성·출력 4항목을 직접 정한다.','구현','coding_instructions.py / coding_examples.py'),
 ('FR04','저장·재사용','지침·선택 설정을 저장하고 새 작업에 재사용한다.','구현','personal_prompts.py'),
 ('FR05','개인·팀 조합','지원 분류의 기준을 비교해 항목별 출처를 고른다.','구현·범위 제한','preference_comparison.py'),
 ('FR06','조합 변경 이력','재조합·선택 되돌림을 별도 항목으로 저장한다.','구현','saved_preference_remix.py / saved_preference_restore.py'),
 ('FR07','인수인계·첨부','목적·진행·남은 일·파일·지침을 공유하고 이어받는다.','구현','handoffs.py / handoff_files.py'),
 ('FR08','업무 지침','24개 템플릿과 요청 구조 점검·작업 공간을 제공한다.','구현','template_library.py / prompt_workspace/'),
 ('FR09','선택적 GEPA','지원 환경에서 원본 고정·보충 안내 탐색·새 저장을 한다.','연결 구현','coding_gepa.py / coding_optimization_jobs.py'),
 ('FR10','답변 확인','형식 단서와 직접 확인 질문을 제공한다.','구현','coding_answer_review.py'),
 ('FR11','초안·작업 복귀','상단 메뉴 이동 뒤 초안과 진행 작업을 복구한다.','미완료','docs/history/2026-11-04_project_review.md'),
]
NFR = [
 ('NFR01','접근 통제','소유자·지정 수신자와 요청 버전을 확인한다.','구현 / 권한 검사 기록'),
 ('NFR02','데이터 일관성','revision 충돌을 거절하고 조합 원본을 보존한다.','구현 / 회귀 확인'),
 ('NFR03','지속성','SQLite 저장 자료를 재시작 후에도 유지한다.','로컬 확인 / 운영 미확인'),
 ('NFR04','비용 제한','GEPA 작업당 요청 32회·성찰 4회, 동시 2개/계정 1개.','구현 / 실비·지연 미측정'),
 ('NFR05','첨부 제한','파일 5MiB·현재 10개·이전 포함 작업당 20MiB.','구현 / 경계·권한 검사'),
 ('NFR06','평가 추적성','평가 버전·별도 과제·실패·미확인을 구분한다.','기록 구현 / 효과 후속 검증'),
 ('NFR07','사용 흐름','선택→생성→저장→재사용과 이동 복귀를 보장한다.','일부 확인 / 복귀 보완 필요'),
 ('NFR08','운영 품질','HTTPS·백업 복구·실제 접속·응답 시간을 확인한다.','계획 / SLA 미설정'),
]

def md_table(head, rows):
    return '\n'.join(['| '+' | '.join(head)+' |','|'+'|'.join(['---']*len(head))+'|']+
                     ['| '+' | '.join(str(x).replace('\n','<br>') for x in r)+' |' for r in rows])+'\n'

def schemas():
    tree = ast.parse((ROOT/'app_db.py').read_text(encoding='utf-8'))
    node = next(n for n in tree.body if isinstance(n, ast.AnnAssign) and getattr(n.target,'id','')=='MIGRATIONS')
    migrations = ast.literal_eval(node.value)
    con = sqlite3.connect(':memory:')
    for script in migrations:
        con.executescript(script)
    names = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    return con, names

def build():
    parts=['''# Revealed 설계문서 · AI/SW융합프로젝트

작성일: 2026-11-05 · 팀원: 윤정우, 고차원

## 1. 목적과 설계 기준

사용자가 고른 선호로 프롬프트를 만들고, 저장한 지침을 새 작업에 다시 사용하는 웹 서비스다.
문서 요약과 코딩을 유지하며, 팀 기준 비교·작업용 조합·인수인계는 지침의 공유와 재사용을 돕는다.
AWS 기능은 이번 수업 범위에서 제외한다. 이번 기능 개발과 고차원의 별도 React 실험은 근거를 구분한다.

이 문서는 11/03~04에 구현한 내용을 11/05에 설계 산출물로 정리한 것이다. 구현 이전에 모든 설계문서가
완성되어 있었다는 뜻은 아니다. 현행 코드는 `a2f1292`, 연구 기록은 `fee9d1c`를 기준으로 한다.
새 코딩 4항목의 직접 선택과 기존 React 3축의 선호 추정은 다른 경로다.
보고서·문서 작성은 기능 수정, 신규 모델 실험, 원격 배포 또는 연구 브랜치 통합을 의미하지 않는다.

## 2. WBS와 역할

금주: 10/30~11/05 · 차주: 11/06~11/12. 실제 구현 날짜는 11/03~04, 설계 문서화는 11/05다.
막대형 WBS는 주간보고서 2쪽에 있다. ●는 해당 주의 확인 실적, ○는 앞으로의 작업 창이다.
담당은 수업에서 정리한 수행 영역과 다음 작업 제안이며, 모든 커밋의 단독 저작자 판정을 뜻하지 않는다.
후속 일정은 수업 피드백에 따라 조정한다. 전체 완료율은 산정하지 않는다.
''']
    weeks=['10/30~11/05','11/06~12','11/13~19','11/20~26','11/27~12/03','12/04~11']
    parts.append(md_table(['ID','단계','작업·산출물','담당','기준']+weeks,
      [[a,b,c,d,e]+['●' if k in done else '○' if k in plan else '' for k in range(6)] for a,b,c,d,e,done,plan in WBS]))
    parts += ['## 3. 기능 요구사항\n',md_table(['ID','기능','요구사항','상태','근거'],FR),
      '''FR05는 같은 분류의 기존 비교 지침에 적용한다. 새 언어별 직접 설정 지침을 기존 React 팀 기준에 자동 조합하지 않는다.
FR08의 템플릿은 기존 선택 비교 6개와 확인·복사·점검용 새 초안 18개로 나뉜다.
FR09는 13개 언어/프레임워크 조합에 실행 경로가 있다는 뜻이며 전체 환경의 개선 효과를 입증한 것은 아니다.

## 4. 비기능 요구사항
''',md_table(['ID','항목','요구사항','현재 확인 상태'],NFR),
      '''NFR07의 합격 기준은 상단 이동 전후 입력 유지 또는 이탈 경고, 계정별 진행 작업 재열람이다. 현재 미완료다.
NFR08의 응답시간·동시 사용자·가용성 수치를 측정 없이 정하지 않는다. 운영 확인 시 조건과 관측치를 기록한다.

## 5. 시스템 구성

```mermaid
flowchart LR
  U[사용자 브라우저] --> UI[React / Vite]
  UI -->|JSON HTTP / 세션 쿠키| API[ApiHandler / Python http.server]
  API --> AUTH[AuthService]
  API --> STORE[개인 지침 / 팀 / 인수인계 저장소]
  AUTH --> DB[(SQLite)]
  STORE --> DB
  API --> BUILD[직접 설정 지침 조립 / 답변 확인]
  API --> OLD[기존 service / engine]
  API --> JOB[CodingOptimizationJobs]
  JOB --> GEPA[GEPA / 환경별 정적 평가]
  OLD --> LLM[외부 모델 API]
  GEPA --> LLM
  GEPA --> CACHE[파일 응답 캐시]
```

`FastAPI`는 생성 코드의 대상 환경 중 하나다. 현재 앱 API 서버 프레임워크는 FastAPI가 아니라 Python 표준 `http.server`다.
직접 설정 지침 조립과 붙여 넣은 답변 확인은 모델 호출·생성 코드 실행을 하지 않는다.
호스팅용 `hosting_server.py`는 React 빌드와 API를 같은 주소에서 제공한다. Docker·영구 저장 설정은 준비했고 공개 운영은 미확인이다.

__UML_CONTENT__

## 7. ERD와 테이블 정의

아래 정의는 `app_db.py`의 migration 1~10을 메모리 SQLite에 적용해 추출한 현행 스키마다.
사용자 DB를 읽거나 변경하지 않는다. JSON 속의 출처 연결은 DB 외래키가 아니며 별도 검증한다.
''']
    con,names=schemas()
    edges=[]
    for name in names:
        for fk in con.execute(f'PRAGMA foreign_key_list("{name}")'):
            col=next(c for c in con.execute(f'PRAGMA table_info("{name}")') if c[1]==fk[3])
            edges.append(f'  {fk[2]} '+('||' if col[3] else '|o')+f'--o{{ {name} : "{fk[3]}"')
    entities=[]
    for name in names:
        foreign={f[3] for f in con.execute(f'PRAGMA foreign_key_list("{name}")')}
        entities.append(f'  {name} {{')
        for _,col,typ,nn,default,pk in con.execute(f'PRAGMA table_info("{name}")'):
            if pk or col in foreign:
                roles=', '.join((['PK'] if pk else [])+(['FK'] if col in foreign else []))
                entities.append(f'    {typ} {col} {roles}')
        entities.append('  }')
    parts.append('```mermaid\nerDiagram\n'+'\n'.join(entities+edges)+'\n```\n')
    meanings={'users':'계정','sessions':'로그인 세션','workspace_projects':'업무 지침 프로젝트','workspace_versions':'저장 버전',
      'workspace_members':'프로젝트 공유 권한','workspace_drafts':'사용자별 작업 사본','usage':'하루 사용량',
      'teams':'팀 기준 그룹','team_members':'팀원별 선택 이력','personal_prompts':'개인 지침·설정·출처',
      'handoffs':'인수인계 현재 상태','handoff_versions':'인수인계 변경 기록','handoff_files':'첨부 원본'}
    for name in names:
        parts.append(f'### `{name}` — {meanings[name]}\n')
        fks={f[3]:f'{f[2]}.{f[4]} / ON DELETE {f[6]}' for f in con.execute(f'PRAGMA foreign_key_list("{name}")')}
        cols=[]
        for cid,col,typ,nn,default,pk in con.execute(f'PRAGMA table_info("{name}")'):
            cols.append([col,typ,'PK '+str(pk) if pk else '', 'NOT NULL' if nn else '명시 없음',str(default) if default is not None else '—',fks.get(col,'—')])
        parts.append(md_table(['컬럼','SQLite 타입','키 순서','NULL 선언','기본값','FK / 삭제 정책'],cols))
        ddl=con.execute('SELECT sql FROM sqlite_master WHERE name=?',(name,)).fetchone()[0]
        parts.append('```sql\n'+ddl+';\n```\n')
    con.close()
    parts += ['''`NULL 선언`은 PRAGMA에 나타난 명시적 선언이다. SQLite rowid/PRIMARY KEY 동작은 원문 DDL을 함께 확인한다.
`personal_prompts.provenance_json`은 조합 출처·직전 저장 ID·스냅샷, `coding_profile_json`은 환경·선호·지침 해시·선택적 GEPA 평가 기록이다.
`handoffs.body_json`은 목적·진행·남은 일·자료 경로·지침·첨부 메타데이터이며 파일 바이트는 `handoff_files.data`에 저장한다.
`usage.subject`와 `team_members.member_key`는 문자열 식별자이며 `users.id`의 외래키로 그리지 않는다.

## 8. 내부·외부 인터페이스 / API 명세

### 8.1 공통 규약

- 서버: `api_server.py` / `ApiHandler`. 개발 프록시와 배포용 동일 출처 경로는 `/api/...`를 사용한다.
- JSON: UTF-8 `application/json`. 일반 본문은 256,000바이트 상한, 로그인한 첨부 경로만 별도 상한이다.
- 인증: `ppt_session` 쿠키. HttpOnly·SameSite=Lax이며 Secure는 서버 설정에 따른다.
- 오류: `{"error":"설명"}`. 400 입력 오류, 401 로그인 필요, 403 권한/출처 거부, 404 없음·접근 불가,
  409 버전 충돌. 경로별 한도·상위 모델 실패는 해당 핸들러 정책을 따른다.
- 아래 명세는 이번 주 핵심 변경 범위다. 기존 전체 workspace/session API의 전수 명세는 별도 확장 범위다.

### 8.2 코딩·보관함 API
''',md_table(['메서드·경로','인증','요청','응답·상태'],[
 ['POST /api/coding-instructions/preview','없음','profile','200 {draft:{profile,prompt}}'],
 ['POST /api/coding-instructions/examples','없음','profile','200 {examples}'],
 ['POST /api/coding-instructions/review','없음','profile, answer, isPatch(선택)','200 {inspection}'],
 ['GET /api/preferences','필수','없음','200 {preferences:[...]}'],
 ['GET /api/preferences/{id}','소유자','없음','200 {preference}'],
 ['POST /api/preferences','필수','title, domainKey, prompt, note(선택), codingProfile(선택)','201 {preference}'],
 ['POST /api/preferences/{id}/update','소유자','title, domainKey, prompt, note(선택), revision','200 {preference} / 409'],
 ['POST /api/preferences/{id}/delete','소유자','revision','200 {ok:true} / 409'],
 ['POST /api/preferences/{id}/compare-team','소유자','revision, teamCode, language(선택)','200 {comparison}'],
 ['POST /api/preferences/{id}/compose-task','소유자','revision, teamCode, teamSnapshot, choices','200 {draft}'],
 ['POST /api/preferences/{id}/save-task','소유자','compose-task 입력 + taskSnapshot, title, note(선택)','201 {preference}'],
 ['POST /api/preferences/{id}/remix-preview','소유자','revision, choices','200 {draft}'],
 ['POST /api/preferences/{id}/restore-preview','소유자','revision, restoreAxes','200 {draft}'],
 ['POST /api/preferences/{id}/remix-save 또는 restore-save','소유자','각 preview 입력 + draftSnapshot, 다른 title, note(선택)','201 {preference}'],
 ['POST /api/preferences/{id}/run','소유자·실제 AI 모드','revision, task, basis; team/custom은 팀·조합 snapshot 추가','200 {output,model,revision,...}; 상위 실패 502'],
 ]),'''### 8.3 Profile 계약과 요청 예시

`profile.language`는 필수 문자열(60자), `framework`는 100자 이하, `extra`는 1,000자 이하이다.
`preferences`에는 아래 네 키를 정확히 넣는다. 각 값은 선택지 중 하나다.

```json
{
  "profile": {
    "language": "TypeScript",
    "framework": "React",
    "preferences": {
      "explanation": "brief",
      "comments": "essential",
      "structure": "compact",
      "output": "complete"
    },
    "extra": ""
  }
}
```

허용값: explanation=brief/steps, comments=essential/detailed, structure=compact/modular,
output=complete/changes. 선택적 `comparison`은 버전·선택 이력·프레임워크 예시 출처를 검증한다.
직접 설정 저장 시 `codingProfile`을 보내면 지침 전문이 서버 조립 결과와 일치해야 한다.
보관함 이름 100자, 본문 20,000자, 설명 1,000자, 계정당 100개 상한이다.
요청 예시는 명세용 입력이며 새 모델 실행 결과가 아니다.

### 8.4 인수인계 API
''',md_table(['메서드·경로','요청','응답·주요 조건'],[
 ['GET /api/handoffs','없음','200 {handoffs}; 로그인 / 소유·수신 목록'],
 ['GET /api/handoffs/{id}','없음','200 {handoff}; 소유자 또는 지정 수신자'],
 ['POST /api/handoffs','title,purpose,progress,remaining,prompt(선택),references(선택)','201 {handoff}; 로그인'],
 ['POST /api/handoffs/{id}/update','생성 필드 + revision','200 {handoff}; 현재 편집 담당자'],
 ['POST /api/handoffs/{id}/share','revision, username','200 {handoff}; 작성자 / 같은 서비스의 다른 계정'],
 ['POST /api/handoffs/{id}/claim, complete, reopen','revision','200 {handoff}; 지정 수신자 / 유효한 현재 상태'],
 ['POST /api/handoffs/{id}/attach','revision, name, data(Base64)','200 {handoff}; 첨부와 버전 함께 저장'],
 ['POST /api/handoffs/{id}/detach','revision, fileId','200 {handoff}; 현재 목록 제외 / 이전 원본 보존'],
 ['GET /api/handoffs/{id}/files/{fileId}?revision={n}&view=1','revision 필수; view=1은 선택','200 바이너리; 현재 권한 + 해당 버전 첨부 목록'],
 ['GET /api/handoffs/{id}/history[/{revision}]','없음','200 {history} 또는 {snapshot}; 공유 시점 이전 수신자 차단'],
 ]),'''### 8.5 선택적 GEPA API
''',md_table(['메서드·경로','요청','응답·상태'],[
 ['GET /api/coding-instructions/optimizations','없음·비로그인 허용','200 {environments,call_limit,retention_seconds,...}'],
 ['POST /api/coding-instructions/optimizations','profile, originalPrompt / 로그인','202 {job}; 환경 활성·원본 일치 확인'],
 ['GET /api/coding-instructions/optimizations/{jobId}','소유 계정','200 {job}; running / done / error'],
 ['POST /api/coding-instructions/optimizations/{jobId}/save','title, humanReview(선택) / 소유 계정','201 {preference}; 서버 보유의 변경된 완료 후보만 저장'],
 ]),'''작업은 메모리에 약 7,200초 보관하며 서버 재시작 후 복구되지 않는다. 영구 작업 큐를 구현했다고 설명하지 않는다.
시작 전 확인과 폴링은 모델 실행 자체가 아니며, POST 시작은 실제 모델 호출을 일으킬 수 있다.
클라이언트가 임의로 전송한 후보 본문·평가 점수·owner 값은 저장 근거로 사용하지 않는다.

### 8.6 외부 인터페이스

| 연계 | 방향·자료 | 실행 조건 | 상태 |
|---|---|---|---|
| 외부 언어 모델 | 서버 → 제공자: 지침·과제 / 제공자 → 서버: 응답 | 실제 AI 모드와 사용자 실행, 환경별 한도·캐시 | 코드 연동; 이번 문서화에서 신규 호출 없음 |
| 사용자가 쓰는 AI 도구 | 사용자가 지침·작업 요청을 복사해 전달 | 명시적 복사 후 사용자가 붙여 넣음 | 자동 전송 API 아님 |
| 첨부 파일 | 브라우저 → 서버: Base64 원본 / 서버 → 권한 있는 사용자: 바이너리 | 저장·버전·권한 검사 | 구현; 첨부 내용은 AI에 자동 전송 안 함 |
| 웹 호스팅 | React 정적 파일 + API / SQLite·캐시 볼륨 | 별도 배포 설정 | 로컬 준비; 공개 서버·HTTPS·백업 확인 남음 |

## 9. 화면 정의·와이어프레임·스토리보드

웹 앱 기준이다. 주간보고서 16쪽은 코딩 핵심 흐름의 와이어프레임, 17~18쪽은 실제 구현 화면이다.

| 화면 ID | 화면 | 입력·주요 행동 | 다음 화면·검증 |
|---|---|---|---|
| UI01 | 시작하기 | 문서 요약 / 코딩 도움 / 팀 업무 정리 | 선택한 흐름 진입 |
| UI02 | 코딩 환경 | 언어·프레임워크 버튼 또는 직접 입력 | 미선택 상태로 시작, 변경 시 선택 출처 초기화 |
| UI03 | 선호 선택 | 4항목 준비 예시 A/B 또는 직접 설정 | 보류는 자동 채우지 않음; 확인 화면에서 결정 |
| UI04 | 지침 확인 | 선택 요약·전문·새 작업 입력·복사·저장 | 설정과 본문 분리; 저장 시 로그인 |
| UI05 | 내 선호 보관함 | 목록·편집·재사용·지원 분류 팀 비교 | revision 확인, 수정 후 설정 불일치 안내 |
| UI06 | 팀 기준 맞추기 | 팀 만들기·초대·선호 반영 | 사용자 명시적 합치기; 자동 합의 아님 |
| UI07 | 작업용 조합 | 개인/팀 항목 선택·미리 보기·새 저장 | 원본 유지; 출처·직전 연결·선택 되돌림 |
| UI08 | 팀 업무 정리 | 목적·진행·남은 일·자료·지침·첨부 | 저장→첨부→수신자 지정→이어받기 |
| UI09 | 템플릿·업무 지침 | 초안 확인·복사·요청 점검·작업 공간 | 지원하는 6개만 선택 비교; 새 18개는 초안 |
| UI10 | 개선·답변 확인 | GEPA 전후 확인 또는 답변 붙여 넣기 | 유료 시작과 단순 확인 구분; 직접 판단 기록 |

### 코딩 스토리보드

1. UI01에서 코딩을 고른다. UI02에서 개발 환경을 정한다.
2. UI03에서 항목별 예시를 읽고 선택한다. 직접 설정으로 전환할 수 있다.
3. UI04에서 네 선택과 지침 전문을 확인한다. 보류한 항목은 직접 결정해야 생성할 수 있다.
4. 로그인 후 이름을 붙여 UI05에 저장한다. 저장된 설정과 지침을 다시 열어 새 작업과 함께 복사한다.
5. 선택적으로 UI10에서 받은 답변을 점검한다. GEPA는 지원 환경과 실제 호출 설정이 준비됐을 때만 별도로 시작한다.
6. 현재 알려진 예외: 상단 메뉴 이동 시 초안 소실, GEPA 작업 재열기 누락. 이 두 흐름은 다음 주 보완 대상이다.

### 인수인계 스토리보드

작성자는 UI08에서 작업을 저장하고 파일을 첨부한 뒤 같은 서비스의 계정을 지정한다.
수신자는 권한 확인 후 자료를 열고 이어서 맡아 진행을 갱신한다. 완료·다시 진행을 할 수 있다.
동시에 수정한 경우 409 충돌을 안내하고 최신 버전을 확인한다. 파일 링크만 아는 제3자는 열 수 없다.

## 10. 완료한 검증과 다음 주 계획

| 구분 | 근거 | 해석 |
|---|---|---|
| 11/04 전체 회귀 | 프론트 86 통과·빌드 통과 / Python 1,083 통과·1 실패·API 16 제외 | 실패 항목만 UTF-8 단독 실행 통과; 전체 재실행 통과로 합산 안 함 |
| 11/04 호스팅 준비 | 관련 서버 68 통과·1 건너뜀 / 프로세스 재시작 후 저장 자료 유지 | 전체 회귀와 중복될 수 있어 개수 합산 안 함; 공개 배포 입증 아님 |
| 11/04 화면 | 격리된 예시 계정의 실제 화면 19장 | 규칙 기반 데모·준비 답변 포함; 신규 유료 AI 성능 실험 아님 |
| 고차원 React 연구 | 1·2·3차 B-A: 스타일 축 +28.89 / +27.78 / +23.33%p, 기능 -1.67 / -16.67 / -6.67%p | 기능 1·2차는 재채점값. 1차 구간은 0 포함, 2·3차 저하 관찰·원인 미분리. 실제 사용자 만족도 아님 |
| 후속 검증 | React의 새 과제·스타일·기능·미확인 기록, 두 계정 권한 시나리오 | 사용자 모집 없이 기술적 적합성과 동작 확인; 만족도·시간 절감 주장 제외 |

다음 주 완료 조건: 문서와 코드 대응 검토, 대표 저장·재사용 시연, 초안·작업 복귀 보완, 연구 변경별 선별 통합과
회귀 결과, 독립 과제 평가표다. 유료 실험은 범위·호출 상한을 정한 뒤 실행한 조건만 보고한다.
4차 코딩 확증 실험·전체 환경 개선 효과·사용자 만족도·공개 배포는 완료 항목에 넣지 않는다.

### React 결과를 읽는 기준과 11/06 동료 검토 반영

실험 **A는 지침 없음(`none`), B는 선택으로 조립한 지침(`rule_based`)**이다. 두 조건 모두 개발 요청은 받으며 추가 시스템 지침이 다르다. 화면에서 사용자가 선택하는 코드 **예시 A/B와는 다른 표기**다. 아래는 B-A의 차이이며 단위는 퍼센트포인트(%p), 괄호는 저장된 95% 부트스트랩 구간이다.

| 차수 | 스타일 축 통과율 B-A (%p) | 기능 통과율 B-A (%p) | 기능 지표 근거 |
|---|---|---|---|
| 1차 | +28.89 [ +22.22, +36.11 ] | -1.67 [ -13.33, +10.00 ] | 실행 검사 수정 후 재채점. 구간이 0 포함, 차이 확인 못함 |
| 2차 | +27.78 [ +22.22, +33.33 ] | -16.67 [ -30.00, -3.33 ] | 실행 검사 수정 후 재채점. 기능 저하 관찰 |
| 3차 | +23.33 [ +16.67, +30.00 ] | -6.67 [ -13.33, -1.67 ] | 새 보류 과제의 기능 저하 관찰 |

기능은 TypeScript 검사·빌드·과제별 고정 시나리오 기준이다. 1차의 구간이 0을 포함하는 것은 **차이가 정확히 0 또는 두 조건이 동등함을 입증했다는 뜻이 아니다.** 기능 저하 원인은 아직 분리하지 못했다. 각 차수는 모의 프로필 4 × 과제 5 × 반복 3 = 60단위이며, 실제 사용자 60명이 아니다. 과제 세트가 달라 차수별 수치를 시간에 따른 개선 추세로 해석하지 않는다.

보고한 기능 미확인 건수(A/B)는 1차 4/0, 2차 4/1, 3차 0/0이다. 따라서 이 수치를 모든 입력의 기능 동일성이나 실제 사용자의 만족도로 일반화하지 않는다. 표는 `summary.paired.rule_based-none`의 기록을 %p로 변환한 값이다. 원본 응답을 새로 생성하거나 평가기를 새로 실행하지 않았다.

1차 재채점 파일은 **A/B의 기능 지표**를 확인하는 데 사용한다. 연구 이력에 따르면 그 파일의 AI 재서술 조건 C는 변경된 검증 문맥으로 캐시를 이용하지 못해 B로 대체되었다. 따라서 1차 AI 재서술 효과(C-B)를 이 재채점 파일에서 새로 판정하지 않는다.

대조 기준은 현재 서비스 README의 이전 요약이 아니라 **연구 커밋 `fee9d1c`의 README와 결과 JSON**이다.

- [연구 README](https://github.com/a77315829-byte/preference-prompt-tool/blob/fee9d1c67ae448dfab88cced704463ecaf9e499e/README.md)
- [1차 재채점 결과](https://github.com/a77315829-byte/preference-prompt-tool/blob/fee9d1c67ae448dfab88cced704463ecaf9e499e/experiments/results/ppc_holdout_behavior_rescored.json)
- [2차 재채점 결과](https://github.com/a77315829-byte/preference-prompt-tool/blob/fee9d1c67ae448dfab88cced704463ecaf9e499e/experiments/results/ppc2_holdout_behavior_rescored.json)
- [3차 결과](https://github.com/a77315829-byte/preference-prompt-tool/blob/fee9d1c67ae448dfab88cced704463ecaf9e499e/experiments/results/rc_holdout_behavior.json)

11/06 동료 검토 반영: 6쪽의 누락된 기능 수치·조건 정의를 보완했다. 20쪽은 커밋 고정 링크에 연구 브랜치 안내를 더했다. 표지의 `2026년 2학기`는 이미 반영된 것을 확인했다. 주간보고 기준일은 11/05를 유지한다.

## 11. 공유와 근거

이 폴더의 보고서·대본·설계문서는 수업 공유용 산출물이다. 새 문서는 로컬에 작성되었으며 원격 업로드는 별도다.
GitHub에 올린 뒤에는 이 Markdown의 상대 링크와 Mermaid 다이어그램으로 공유할 수 있다.
기존 멘토링 계획의 다른 팀원 명단과 사용자 모집 목표는 이번 수업의 2인 R&R에 적용하지 않는다.

- [현재 구현 코드](https://github.com/a77315829-byte/preference-prompt-tool/tree/a2f12928717c11555c7376d0efdd27e0b0703b51)
- [고차원 연구 브랜치 기준](https://github.com/a77315829-byte/preference-prompt-tool/tree/fee9d1c67ae448dfab88cced704463ecaf9e499e)
- [DB 스키마](../../../app_db.py), [API](../../../api_server.py), [보관함](../../../personal_prompts.py), [인수인계](../../../handoffs.py)
- [전체 점검 기록](../../history/2026-11-04_project_review.md), [호스팅 준비](../../history/2026-11-04_hosting_preparation.md)
- [화면 출처](../../screenshots/current/capture-info.json), [제품 방향](../../product_direction_small_teams.md)

기능 요구사항과 NFR의 상태는 코드·해당 기록을 기준으로 한다. 이번 문서 작성 중 애플리케이션 전체 검사를 새로 실행한 것은 아니다.
''']
    content = '\n'.join(parts).replace('__UML_CONTENT__', (HERE/'uml_details.md').read_text(encoding='utf-8'))
    OUT.write_text(content,encoding='utf-8')
    print('Design document:',OUT.name,'tables:',len(names))

if __name__=='__main__':
    build()
