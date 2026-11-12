# 6. HTTP API 및 외부 인터페이스 명세

현재 `api_server.py`의 경로 분기와 호출되는 validator·Store를 정적으로 대조한 명세다. **GET/POST 90개 method/path 조합**을 식별했으며 모든 경로에 응답하는 OPTIONS는 별도로 셌다. 배포 주소에 접근해 동작을 시험한 결과가 아니다. 기준은 2026-11-12 로컬 개발본이고, 필드와 소스 위치를 담은 원자료는 `api-inventory.json`이다.

## 6.1 공통 전송 규칙

| 항목 | 현재 규약 | 클라이언트 책임 |
|---|---|---|
| 기본 경로 | 동일 출처의 /api, 개발 시 Vite 프록시 | 서버 키나 모델 이름을 프론트에 넣지 않음 |
| 메서드 | 조회 GET, 명령 POST, preflight OPTIONS | 수정·삭제에도 현재 구현의 POST action 경로 사용 |
| 본문 | UTF-8 JSON 객체; 일반 최대 256,000 bytes | 목록·문자열만 최상위로 보내지 않음 |
| 첨부 본문 | attach 전용 Base64 JSON 상한 | 파일 크기와 Base64 확장량을 구분 |
| 응답 | JSON UTF-8, Cache-Control:no-store | HTTP status와 payload의 status를 구분 |
| 인증 | HttpOnly 세션 쿠키, SameSite=Lax | 토큰을 JS 저장소에 따로 보관하지 않음 |
| 쿠키 Secure | 설정에 따라 활성화 | 인터넷 배포 시 HTTPS와 설정을 함께 확인 |
| CORS·POST 출처 | 허용 Origin 또는 같은 Host 계열을 검사 | 허용 목록이 배포망 전체 보안 정책을 대신하지 않음 |
| 오류 | 대체로 error 문자열, 적절한 HTTP 상태 | 원래 입력을 보존하고 안내; 유료 작업 자동 반복 금지 |
| 모델 선택 | 서버 환경 설정이 결정 | 요청 model 필드로 임의 모델을 고를 수 없음 |
| trailing slash | 경로 끝 / 제거 후 분기 | 문서의 정규 경로로 요청 |
| OPTIONS | 204; 허용 Origin에 CORS 헤더 | 이 응답이 실제 인증·기능 사용 가능을 뜻하지 않음 |

개발용 ApiHandler의 POST 다른 사이트 검사는 Origin이 없으면 통과시키며 전달 Host 헤더를 고려한다. 운영용 hosting_server.HostedHandler는 이 검사를 override해 공개 Host 기준으로 Origin을 대조하고 X-Forwarded-Host를 승인 근거로 신뢰하지 않는다. 두 핸들러의 프록시 가정을 구분해야 하며 모든 외부망·프록시 조합에 대한 CSRF 안전성 검증이나 보안 인증을 뜻하지 않는다. Content-Type을 표에 적은 JSON 형식으로 보내는 것이 클라이언트 규약이며 서버는 실제 바이트를 JSON 객체로 해석한다.

## 6.2 오류·동시성 계약

| 상태 | 실제 사용 사례 | 사용자 처리 |
|---|---|---|
| 200 | 조회·수정·미리 보기·규칙 확인 | 반환 자료로 현재 상태 갱신 |
| 201 | 비교 시작, 개인 지침·팀·인수인계·작업 비교 생성 | 서버가 반환한 ID·revision 보관 |
| 202 | 개선 작업 접수 또는 이미 진행 중 | 해당 세션/job 조회로 진행 확인 |
| 400 | 입력·조건·상한·현재 단계 오류 | 입력 또는 단계 수정; 무조건 재시도하지 않음 |
| 401 | 계정 기능에 로그인 없음 | 로그인 후 원래 흐름으로 복귀 |
| 403 | 다른 사이트 POST, 역할 부족, 가입 닫힘 등 | 권한이나 요청 경로 확인 |
| 404 | 없는 자료·타 계정 자료·만료 세션·지원하지 않는 경로 | 목록 재조회; 숨겨진 자료 존재를 추측하지 않음 |
| 409 | 오래된 비교 pairId, 저장 revision·팀 snapshot 불일치 | 입력 보존 후 최신 상태를 다시 열고 재확인 |
| 429 | 인증 실패·가입 시도 제한 | 잠시 기다리거나 계정 정보 확인 |
| 500 | 일반 서버/공급자 예외의 안전한 요약 | 원시 공급자 오류 대신 안내; 서버 운영 확인 |
| 502 | 보관 지침으로 실행 중 외부 생성 실패 | 원본 지침 유지, 명시적으로 다시 시도 |

모든 상한 오류가 429인 것은 아니다. 일일 모델 횟수·저장 개수 같은 제한은 해당 경로에서 400 또는 비교 데모 전환으로 나타날 수 있다. 보관함·인수인계·새 코딩 작업의 revision은 양의 정수이며 boolean은 정수로 인정하지 않는다. API 단에서 전달된 현재값과 Store의 트랜잭션 안 실제값을 대조한다.

비교 세션은 pairId, 개인/팀 조합은 revision과 snapshot을 쓴다. snapshot은 현재 지침·팀·선택의 지문이며 권한을 주는 토큰이 아니다. 작업 공간의 명시 버전 저장은 버전을 덧붙이는 방식이고 개인 보관함의 409 규약과 동일한 낙관적 잠금을 모든 경로에 제공한다고 표현하지 않는다.

## 6.3 전체 경로 목록

물음표는 선택 필드다. profile·project 같은 중첩 자료는 뒤의 상세 스키마를 따른다. 모델 없음은 이 요청의 처리 중 유료 모델 API를 부르지 않는다는 뜻이며 서버 전송이 없다는 뜻이 아니다. ID별 구현 위치와 부작용은 원자료에 함께 기록했다.

### 상태·계정

| ID·방식·경로 | 요청 핵심 | 응답 | 접근·모델 호출 |
|---|---|---|---|
| API-001 · GET /api/health | 없음 | ok,demoAvailable,live,liveConfigured | 공개; 모델 없음 |
| API-002 · GET /api/templates | 없음 | templates[] | 공개; 모델 없음 |
| API-003 · GET /api/auth/me | 없음 | user,signupOpen,ownedShared,quota | 쿠키 선택; 모델 없음 |
| API-004 · POST /api/auth/signup | username,password | user + Set-Cookie | 공개·가입허용; 모델 없음 |
| API-005 · POST /api/auth/login | username,password | user + Set-Cookie | 공개; 모델 없음 |
| API-006 · POST /api/auth/logout | {} | user:null + 쿠키만료 | 쿠키 선택; 모델 없음 |
| API-007 · POST /api/auth/password | current,new | user + 새쿠키 | 로그인·현재 비밀번호; 모델 없음 |
| API-008 · POST /api/auth/delete | password | user:null + 쿠키만료 | 로그인·비밀번호 재확인; 모델 없음 |

### 비교 세션·요약 조건

| ID·방식·경로 | 요청 핵심 | 응답 | 접근·모델 호출 |
|---|---|---|---|
| API-009 · POST /api/sessions | domainKey,sourceText,totalRounds?,templateId? | session | 공개; 실제 모드에서 호출 가능 |
| API-010 · GET /api/sessions/{id} | 경로 id | session | 세션 ID; 계정소유검사 없음; 모델 없음 |
| API-011 · POST /api/sessions/{id}/choices | pairId,chosen | session | 세션 ID; 실제 모드에서 호출 가능 |
| API-012 · POST /api/sessions/{id}/undo | {} | session | 세션 ID; 캐시 재사용 |
| API-013 · POST /api/sessions/{id}/optimize | {} | 202 session | 끝난 실제 비교 세션; 실제 모드에서 호출 가능 |
| API-014 · POST /api/summary-contract | domainKey,profile,sourceText,requiredSentences?,resolution? | status,profiles,conflict,prompts,task_requests,notices | 공개; 모델 없음 |

### 코딩 지침·GEPA

| ID·방식·경로 | 요청 핵심 | 응답 | 접근·모델 호출 |
|---|---|---|---|
| API-015 · POST /api/coding-instructions/preview | profile | draft:{profile,prompt} | 공개; 모델 없음 |
| API-016 · POST /api/coding-instructions/examples | profile,protocol? | examples | 공개; 모델 없음 |
| API-017 · POST /api/coding-instructions/review | profile,answer,isPatch? | inspection | 공개; 모델 없음 |
| API-018 · GET /api/coding-instructions/optimizations | 없음 | enabled,reason,environments,call_limit,retention_seconds | 공개; 모델 없음 |
| API-019 · POST /api/coding-instructions/optimizations | profile,originalPrompt | 202 job | 로그인; 실제 모드에서 호출 가능 |
| API-020 · GET /api/coding-instructions/optimizations/recent | 없음 | jobs | 로그인 소유자; 모델 없음 |
| API-021 · GET /api/coding-instructions/optimizations/{jobId} | jobId | job | 로그인 소유자; 모델 없음 |
| API-022 · POST /api/coding-instructions/optimizations/{jobId}/save | title,humanReview? | 201 preference | 로그인 소유자; 모델 없음 |

### 기존 비교 팀

| ID·방식·경로 | 요청 핵심 | 응답 | 접근·모델 호출 |
|---|---|---|---|
| API-023 · GET /api/teams | 없음 | teams | 로그인; 모델 없음 |
| API-024 · GET /api/teams/{code} | code | team | 계정 팀은 참여 범위; 익명 체험 공개; 모델 없음 |
| API-025 · POST /api/teams | name,domainKey? | 201 team | 쿠키 선택; 모델 없음 |
| API-026 · POST /api/teams/{code}/invitation | enabled:boolean | team | 로그인 팀장; 모델 없음 |
| API-027 · POST /api/teams/{code}/members | sessionId,name?,requireExisting? | team | 계정 팀 로그인·열린 초대; 익명 체험 별도; 모델 없음 |

### 개인 보관함·재조합

| ID·방식·경로 | 요청 핵심 | 응답 | 접근·모델 호출 |
|---|---|---|---|
| API-028 · GET /api/preferences | 없음 | preferences | 로그인 소유자; 모델 없음 |
| API-029 · POST /api/preferences | title,domainKey,prompt,note?,codingProfile? | 201 preference | 로그인; 모델 없음 |
| API-030 · GET /api/preferences/{id} | id | preference | 로그인 소유자; 모델 없음 |
| API-031 · POST /api/preferences/{id}/update | revision,title,domainKey,prompt,note? | preference | 로그인 소유자; 모델 없음 |
| API-032 · POST /api/preferences/{id}/delete | revision | ok:true | 로그인 소유자; 모델 없음 |
| API-033 · POST /api/preferences/{id}/remix-preview | revision,choices | draft | 로그인 소유자; 모델 없음 |
| API-034 · POST /api/preferences/{id}/remix-save | revision,choices,draftSnapshot,title,note? | 201 preference | 로그인 소유자; 모델 없음 |
| API-035 · POST /api/preferences/{id}/restore-preview | revision,restoreAxes | draft | 로그인 소유자; 모델 없음 |
| API-036 · POST /api/preferences/{id}/restore-save | revision,restoreAxes,draftSnapshot,title,note? | 201 preference | 로그인 소유자; 모델 없음 |
| API-037 · POST /api/preferences/{id}/compare-team | revision,teamCode,language? | comparison | 로그인 소유자·팀 읽기 권한; 모델 없음 |
| API-038 · POST /api/preferences/{id}/compose-task | revision,teamCode,language?,teamSnapshot,choices | draft | 로그인 소유자·팀 읽기 권한; 모델 없음 |
| API-039 · POST /api/preferences/{id}/save-task | revision,teamCode,language?,teamSnapshot,choices,taskSnapshot,title,note? | 201 preference | 로그인 소유자·팀 읽기 권한; 모델 없음 |
| API-040 · POST /api/preferences/{id}/run | revision,task,basis?,teamCode?,teamSnapshot?,teamLanguage?,choices?,taskSnapshot? | output,model,revision,preference_id,basis,team_code,team_snapshot,task_snapshot | 로그인 소유자·선택시 팀 권한; 실제 모드에서 호출 가능 |

### 새 코딩 팀·내보내기·작업 비교

| ID·방식·경로 | 요청 핵심 | 응답 | 접근·모델 호출 |
|---|---|---|---|
| API-041 · POST /api/coding-work/exports | prompt,title?,target?,existing? | export | 공개; 모델 없음 |
| API-042 · POST /api/coding-work/resolve | profile 또는 preferenceId+preferenceRevision,teamSelection? | draft | 로그인; 모델 없음 |
| API-043 · POST /api/coding-work/save | resolve 입력,snapshot,title,note? | 201 preference | 로그인 소유자; 모델 없음 |
| API-044 · POST /api/coding-work/teams | name,profile,rules? | 201 team | 로그인; 모델 없음 |
| API-045 · GET /api/coding-work/teams/{code} | code | team | 로그인 참여자; 모델 없음 |
| API-046 · POST /api/coding-work/teams/{code}/join | {} | team | 로그인·열린 초대 또는 기존 참여; 모델 없음 |
| API-047 · POST /api/coding-work/teams/{code}/update | revision,profile,rules? | team | 로그인 팀장; 모델 없음 |
| API-048 · POST /api/coding-work/trials | resolve 입력,snapshot,title,task,model,tool,context | 201 trial | 로그인; 모델 없음 |
| API-049 · GET /api/coding-work/trials | 없음 | trials | 로그인 소유자; 모델 없음 |
| API-050 · GET /api/coding-work/trials/{id} | id | trial | 로그인 소유자; 모델 없음 |
| API-051 · POST /api/coding-work/trials/{id}/timer | revision,operation,arm?,phase? | trial | 로그인 소유자; 모델 없음 |
| API-052 · POST /api/coding-work/trials/{id}/result | revision,arm,outcome,evidence?,answer?,passed_tests?,total_tests? | trial | 로그인 소유자; 모델 없음 |
| API-053 · POST /api/coding-work/trials/{id}/preference | revision,preference,reason? | trial | 로그인 소유자; 모델 없음 |
| API-054 · POST /api/coding-work/trials/{id}/delete | revision | trial:null | 로그인 소유자; 모델 없음 |

### 인수인계·첨부

| ID·방식·경로 | 요청 핵심 | 응답 | 접근·모델 호출 |
|---|---|---|---|
| API-055 · GET /api/handoffs | 없음 | handoffs | 로그인 작성자/현재 수신자; 모델 없음 |
| API-056 · POST /api/handoffs | title,purpose,progress,remaining,prompt?,references? | 201 handoff | 로그인; 모델 없음 |
| API-057 · GET /api/handoffs/{id} | id | handoff | 로그인 작성자/현재 수신자; 모델 없음 |
| API-058 · GET /api/handoffs/{id}/history | id | history | 로그인 작성자/현재 수신자; 모델 없음 |
| API-059 · GET /api/handoffs/{id}/history/{revision} | id,revision | snapshot | 로그인 + 공유 시작 이후 버전; 모델 없음 |
| API-060 · GET /api/handoffs/{id}/files/{fileId} | revision 필수 query,view=1 선택 | 바이너리 + 보안 헤더 | 로그인 + 요청 버전 첨부권한; 모델 없음 |
| API-061 · POST /api/handoffs/{id}/update | revision,title,purpose,progress,remaining,prompt?,references? | handoff | 로그인·현재 편집 담당자; 모델 없음 |
| API-062 · POST /api/handoffs/{id}/share | revision,username | handoff | 로그인·이어받기 전 작성자; 모델 없음 |
| API-063 · POST /api/handoffs/{id}/claim | revision | handoff | 로그인·shared의 지정 수신자; 모델 없음 |
| API-064 · POST /api/handoffs/{id}/complete | revision | handoff | 로그인·active의 지정 수신자; 모델 없음 |
| API-065 · POST /api/handoffs/{id}/reopen | revision | handoff | 로그인·done의 지정 수신자; 모델 없음 |
| API-066 · POST /api/handoffs/{id}/attach | revision,name,data(Base64) | handoff | 로그인·현재 편집 담당자; 모델 없음 |
| API-067 · POST /api/handoffs/{id}/detach | revision,fileId | handoff | 로그인·현재 편집 담당자; 모델 없음 |

### 요청 점검·작업 공간 처리

| ID·방식·경로 | 요청 핵심 | 응답 | 접근·모델 호출 |
|---|---|---|---|
| API-068 · POST /api/polish/checklist | prompt | checklist | 공개; 모델 없음 |
| API-069 · POST /api/polish | prompt | checklist,suggestions,revisedPrompt | 공개·실제 생성 모드; 실제 모드에서 호출 가능 |
| API-070 · GET /api/workspace/sample | 없음 | project,status,input,live,notes | 공개; 모델 없음 |
| API-071 · POST /api/workspace/structure | description,title?,exampleOutput? | project,status,notes,cached | 공개; 실제 모드에서 호출 가능 |
| API-072 · POST /api/workspace/status | project | project,status | 공개; 모델 없음 |
| API-073 · POST /api/workspace/resolve | project,questionId,answer,target | project,status | 공개; 모델 없음 |
| API-074 · POST /api/workspace/confirm | project | project,status | 공개; 모델 없음 |
| API-075 · POST /api/workspace/build | project | project,status | 공개; 모델 없음 |
| API-076 · POST /api/workspace/run | project,input | run | 공개; 실제 모드에서 호출 가능 |
| API-077 · POST /api/workspace/suggest | project | suggestions,notes,cached,artifact_revision | 공개; 실제 모드에서 호출 가능 |
| API-078 · POST /api/workspace/apply-suggestions | project,suggestions,allowRuleChanges? | system_prompt,touches_rules | 공개; 모델 없음 |
| API-079 · POST /api/workspace/trial-suggestions | project,suggestions,input | baseline,results | 공개; 실제 모드에서 호출 가능 |
| API-080 · POST /api/workspace/export | project,input?,includeData? | filename,zipBase64 | 공개; 모델 없음 |

### 작업 공간 저장·공유

| ID·방식·경로 | 요청 핵심 | 응답 | 접근·모델 호출 |
|---|---|---|---|
| API-081 · GET /api/workspace/projects | 없음 | projects | 로그인 권한 범위; 모델 없음 |
| API-082 · GET /api/workspace/projects/{id} | id | id,role,owner,project,versions,draft,members? | 로그인 owner/editor/viewer; 모델 없음 |
| API-083 · GET /api/workspace/projects/{id}/versions/{n} | id,n | project | 로그인 읽기 권한; 모델 없음 |
| API-084 · POST /api/workspace/projects | project,label? | version,copied,id,role,owner,project,versions,draft,members? | 로그인; viewer는 자기 사본; 모델 없음 |
| API-085 · POST /api/workspace/projects/{id}/share | username,role | members | 로그인·owner; 모델 없음 |
| API-086 · POST /api/workspace/projects/{id}/unshare | username | members | 로그인·owner; 모델 없음 |
| API-087 · POST /api/workspace/projects/{id}/draft | project | saved_at | 로그인·owner/editor; 모델 없음 |
| API-088 · POST /api/workspace/projects/{id}/discard-draft | {} | discarded | 로그인·개인 draft 접근; 모델 없음 |
| API-089 · POST /api/workspace/projects/{id}/restore | version | 새 저장 버전 및 overview | 로그인·owner/editor; 모델 없음 |
| API-090 · POST /api/workspace/projects/{id}/delete | {} | deleted | 로그인·owner; 모델 없음 |

## 6.4 계정·현재 서비스 상태

username은 영문 대소문자·숫자·밑줄·점·하이픈으로 된 3~30자다. 비밀번호는 8~128자다. 가입 허용은 서버가 정하며 가입·로그인 성공은 user 객체와 세션 쿠키를 반환한다. user는 id·username만 포함한다. GET auth/me의 user=null은 비로그인 상태이고 오류 응답이 아니다.

| 요청 | 필수 입력·검증 | 반환·부작용 |
|---|---|---|
| signup | username, password; 중복·가입 제한 확인 | 계정·세션 생성, user, Set-Cookie |
| login | username, password | 새 세션; 실패 시 아이디/주소별 횟수 집계 |
| logout | 빈 객체 허용 | 현재 토큰 폐기, 쿠키 만료, user:null |
| password | current, new; 현재 비밀번호 재확인 | 비밀번호 변경, 세션 갱신 |
| delete | password 재확인 | 계정 삭제, 관계별 CASCADE/SET NULL 적용, 쿠키 만료 |
| me | 입력 없음 | user, signupOpen, ownedShared, quota |
| health | 입력 없음 | ok, demoAvailable, live, liveConfigured |

auth/me의 ownedShared는 계정 삭제 전에 사라질 소유 공유 프로젝트 수를 알리는 값이다. 전체 저장 자료를 모두 세는 범용 삭제 미리 보기로 해석하지 않는다. quota는 작업 종류별 남은 횟수이며 남은 금액이 아니다. 인증 실패 제한은 메모리 카운터이므로 프로세스 재시작으로 초기화될 수 있다.

## 6.5 비교 세션 요청·응답

| 시작 필드 | 형식·규칙 | 비고 |
|---|---|---|
| domainKey | coding 기본값; 허용 도메인 이름 | coding, review, email, summarization, summarization_ko, summarization_hybrid, macsum_eval_agent |
| sourceText | 문자열화 후 trim, 빈 값 거절 | 기존 비교 경로는 12,000자에서 잘라서 전달한다 |
| totalRounds | 정수로 변환 후 1~8 범위 제한 | 생략 시 서비스 기본값 |
| templateId | 선택 템플릿 ID | 없거나 다른 도메인의 ID는 거절 |
| demoMode/model | 서버가 결정 | 요청 필드로 실제 모드·비싼 모델을 강제하지 못함 |

서비스 화면의 대표 분류와 API 허용 도메인 목록은 다르다. 허용 목록의 연구·과거 경로가 모두 시작 화면의 주요 제품이라는 뜻은 아니다. 새 요약 조건 API는 비교 시작과 달리 12,000자 초과 원문을 자르지 않고 거절한다. 두 동작을 동일하다고 문서화하지 않는다.

| session 주요 필드 | 의미 |
|---|---|
| session_id, domain_key, source_text, model | 비교 ID·도메인·처리 원문·서버 모델 |
| demo_mode, demo_reason | 무료 데모 여부와 전환 이유 |
| history, answered, round, total_rounds, round_limit | 순서 있는 선택·진행 상태 |
| pair | 현재 pair_id와 a/b 예시; 완료하면 없을 수 있음 |
| axes | 추정 값·구분 횟수 등 표시 자료 |
| done, completion_reason, undecided_axes | 완료·종료 이유·확정하지 못한 축 |
| prompt, prompts, prompt_language | 완료 지침과 지원 언어별 본문 |
| exports, exports_by_language | 도구별 내려받기 자료 |
| optimize_status, optimize_progress | 기존 비교 GEPA의 진행 상태 |
| optimize_changed, optimize_report | 실제 지침 변화 여부·개선 근거 |

demo_reason은 live_disabled, api_key_missing, daily_limit, generation_failed 같은 값을 갖는다. 실제 생성 실패 후 데모로 바뀌어도 기존 선택 이력은 이어갈 수 있다. 메모리 세션은 서버 재시작·보관 제한으로 사라질 수 있다. 계정 저장소와 다르게 ID 기반이며 계정 소유권 검사가 없는 점은 운영 보완 대상이다.

choice는 pairId와 chosen=a/b/tie를 보낸다. 지나간 pairId를 재전송하면 409다. undo는 이전 이력을 제거하고 최적화 보고를 정리한다. optimize는 done·실제 생성 세션·정할 수 있는 선호를 요구한다. 진행 중이면 같은 세션을 202로 반환하고 세션별 최적화 횟수 제한을 적용한다.

## 6.6 요약 조건 계약

| 필드 | 제약 | 사용 목적 |
|---|---|---|
| domainKey | summarization 또는 summarization_ko | 언어별 기본 도메인 |
| profile.length | short, normal, long | 분량 조건 |
| profile.extractiveness | normal, high, fully | 재서술/원문 표현 조건 |
| profile.topic | 선택 문자열, 300자 이하 | 이번 요약의 초점 |
| sourceText | 1~12,000자, 초과 자동 절단 없음 | 보존 문장 대조 |
| requiredSentences | 문자열 목록, 최대 8개, 중복 불가 | 현재 원문의 완전한 문장과 일치해야 함 |
| resolution | 선택 expand/rephrase/keep_limits | 실제 분량·완전 발췌 충돌이 있을 때만 허용 |

결과는 version=1, status, available_sentences, required_sentences, original_profile, effective_profile, conflict, resolution, notices, prompts, task_requests다. 충돌이 있으면 선택한 서로 다른 문장 수와 최대 문장 수를 conflict에 넣는다. 미해결 상태에서는 prompts와 task_requests가 빈 객체다.

prompts는 en·ko 재사용 지침만 포함한다. task_requests는 그 지침과 이번 원문·고른 문장을 포함한다. 어느 쪽도 이 요청 자체로 저장하지 않는다. ready는 규칙상 조립이 가능함을 뜻하고 의미 보존·사실성·핵심 내용 자동 판정 결과가 아니다.

## 6.7 코딩 profile·예시·직접 검토

| profile 필드 | 형식·상한 | 허용 값 |
|---|---|---|
| language | 필수, 한 줄 1~60자 | 목록 언어 또는 직접 입력 |
| framework | 선택, 한 줄 0~100자 | 실제 문자열; 지원 GEPA 여부와 별개 |
| extra | 선택 0~1,000자 | 개인 추가 선호 |
| preferences.explanation | 필수 | brief / steps |
| preferences.comments | 필수 | essential / detailed |
| preferences.structure | 필수 | compact / modular |
| preferences.output | 필수 | complete / changes |
| comparison | 선택, version·choices 등 | 버전 1~4의 원래 검증 규칙 |

preferences는 위 네 키를 정확히 갖춰야 한다. comparison.choices와 현재 선택이 다르면 거절한다. 최신 비교 기록은 환경·예시 ID·순서·선택을 다시 검증한다. 지원하지 않는 임의 언어에도 직접 지침 조립은 가능하지만 예시 비교는 준비된 언어만 가능하다.

preview는 draft:{profile,prompt}를 반환한다. examples는 protocol=adaptive-v1이면 현재 적응형 준비 예시, repeated-v1이면 기존 반복 프로토콜, 그 외는 기본 예시를 반환한다. 과거 프로토콜의 접근 경로가 남아 있다는 사실을 새 화면에서 권장하거나 임의로 과거 기록을 최신 기록으로 바꾼다는 뜻으로 해석하지 않는다.

review의 answer는 1~24,000자이고 isPatch는 선택 boolean이다. inspection은 version, preferences, manual_required, observations, guidance를 반환한다. 코드 밖 설명 길이·단계 표시는 참고 검사하며 comments·structure·output은 직접 확인이 필요하다. 이 API는 타입 검사나 실제 렌더링을 하지 않는다.

## 6.8 코딩 GEPA 작업 인터페이스

| 단계 | 요청·조건 | 응답 의미 |
|---|---|---|
| 환경 조회 | GET optimizations | environments별 enabled·reason·evaluation_scope, call_limit, retention_seconds |
| 시작 | profile, originalPrompt; 로그인, 지원 환경·모델·도구 확인 | 202 job; 실제 호출이 시작될 수 있음 |
| 최근 작업 | GET recent; 로그인 계정 | 최대 최근 20개 jobs |
| 진행 조회 | GET jobId; 본인 작업 | status·stage·model_calls·result·error |
| 채택 저장 | title, 선택 humanReview | 서버 보유 결과의 새 preference |

시작 시 originalPrompt는 서버가 profile로 다시 조립한 원본과 정확히 같아야 한다. 클라이언트가 보낸 임의 후보·평가·owner 자료로 저장하지 않는다. job의 결과가 완료되었고 changed=true일 때만 개선 후보 저장을 허용한다. 저장된 job을 다시 저장하면 같은 저장 항목을 돌려준다.

humanReview는 과제 ID → original/candidate → explanation/comments/structure/output의 판단이며 match·needs_work·unsure만 받는다. 해당 서버 결과의 과제 ID와 개선 여부를 검증한다. 직접 판단은 후보 선택 점수로 되먹임하지 않는다.

작업당 모델 최대 32회·성찰 최대 4회, 서버 동시 2개·계정 1개, 공통 일일 개선 횟수 제한을 적용한다. 환경 지원은 FastAPI, Spring Boot, Flask, Django, JS/TS React·Express·Vue·Next.js, TS NestJS의 현재 13조합이다. 형식·제한 AST 검사는 실제 환경의 컴파일·서버·브라우저 실행을 대신하지 않는다. Node 도구가 필요한 환경은 도구가 없으면 시작 전에 비활성화한다.

## 6.9 개인 지침 저장과 작업용 조합

| 저장 필드 | 제약 |
|---|---|
| title | 1~100자 |
| domainKey | coding, summarization, summarization_ko |
| prompt | 1~20,000자 |
| note | 선택 0~1,000자 |
| codingProfile | 선택; coding 분류와 서버 조립 본문 일치 필요 |
| revision | 수정·삭제·비교·실행 시 현재 양의 정수 |

목록은 본문 전체 대신 제목·분류·revision·개발 환경·lineage를 보낸다. 상세는 prompt와 profile·optimization·team_context·provenance 및 현재 본문 일치 여부를 포함한다. 일반 create의 body에 임의 provenance를 넣어 출처를 위조할 수 없도록 서버의 별도 경로만 전달한다.

compare-team은 팀 읽기 권한·같은 domainKey·개인 revision을 확인한다. compose-task는 비교 당시 teamSnapshot과 각 차이 항목의 choices를, save-task는 추가로 taskSnapshot을 확인한다. save-task는 당시 출처를 보존한 새 항목을 만든다.

remix-preview/save는 저장된 출처의 두 값을 다시 고르는 choices를 받는다. restore-preview/save는 바뀐 축 중 restoreAxes를 선택한다. 저장에는 draftSnapshot과 기존 항목과 다른 title이 필요하다. 원본과 과거 출처를 덮어쓰지 않는다.

run의 task는 1~12,000자이고 basis는 personal 기본값, team, custom이다. team/custom은 같은 분류의 접근 가능한 팀과 최신 팀 지문을 요구한다. custom은 선택한 조합 지문도 확인한다. 새 4항목 coding_profile에 기존 React 팀 집계를 적용하는 요청은 거절한다. 실제 모드와 키가 없으면 복사 사용 안내를 반환한다. 모델 답변은 반환하지만 이 경로 자체로 보관함 지침을 변경하지 않는다.

## 6.10 팀 기준·내보내기 계약

| 팀 구분 | 생성·참여 입력 | 읽기·변경 규칙 |
|---|---|---|
| 기존 비교 팀 | name·domainKey, 완료 sessionId | 계정 팀/익명 체험 구분; 완료 선택 이력을 추가 |
| 새 coding_profile 팀 | name·profile·rules | 로그인, 팀장의 네 항목 기본값·필수 규칙 |
| 초대 관리 | code·enabled boolean | 팀장만 닫기/재개 |
| 새 팀 수정 | revision·profile·rules | 팀장만, 언어·프레임워크 고정 |

새 팀 이름은 1~60자, 규칙은 최대 12개·각 1~400자다. 팀 프로필에는 개인 extra·comparison을 공유하지 않는다. resolve의 teamSelection은 code·revision·choices를 갖고 choices는 개인과 팀이 다른 네 항목에 대해 personal/team을 정확히 지정한다. 필수 규칙은 결과 지침에 포함하고 기존 비교 출처를 새 혼합 profile의 근거로 유지하지 않는다.

resolve는 profile 직접 입력 또는 preferenceId+preferenceRevision으로 시작한다. 저장된 지침의 profile hash가 본문과 맞지 않으면 재사용을 거절하고 설정으로 다시 만들도록 안내한다. save와 trials 생성은 resolve에서 본 snapshot이 현재 계산값과 일치해야 한다.

exports는 prompt 1~20,000자, title 최대 100자, target, existing 최대 40,000자를 받는다. target은 agents_md, claude_code, copilot, cursor, markdown이다. 반환은 파일명·경로·content·diff·targets·scope·verification이다. 기존 생성 표시 영역을 대체하거나 끝에 새 영역을 붙인 미리 보기이며 서버가 실제 저장소 파일을 쓰지 않는다. 기존 Cursor 본문 자동 병합은 지원하지 않는다.

## 6.11 실제 작업 비교 기록

| 입력/상태 | 제약·의미 |
|---|---|
| title, task | 이름 100자, 작업 요청 10,000자 |
| model, tool | 모델·설정 200자, 사용 도구 100자 |
| context | 저장소·버전·완료 조건 3,000자 |
| source, prompts | 서버가 고정한 profile·팀 출처·일반/선택 지침 |
| order | general/selected 제시 순서 |
| active | 실행 중 arm·phase·서버 시작 시각 또는 null |
| arms | setup/edit 시간·측정 여부·결과·근거·답변·테스트 수 |
| comparison | 시간 측정 완료·기능 확인 완료·시간차 등 계산값 |

계정당 최대 100개 기록이며 해당 계정의 여러 기록을 통틀어 타이머는 동시에 하나만 진행할 수 있다. timer의 operation은 start/pause, arm은 general/selected, phase는 setup/edit다. setup은 준비·요청·응답 대기, edit는 답변 수정·검사를 합친 시간이며 검사용 세 번째 타이머는 없다. pause 시 서버 경과 시간을 더하고 timed를 true로 바꾼다. 실행 중인 타이머가 있으면 기능 결과 저장·삭제를 거절한다.

result의 outcome은 unverified·pass·fail·blocked다. pass/fail은 evidence 1~4,000자를 요구한다. answer는 선택 20,000자까지 보관한다. passed_tests와 total_tests를 쓰면 둘 다 정수이고 0≤passed≤total≤100000, total>0이어야 하며 pass에 일부 실패를 기록하지 못한다.

preference는 general/selected/tie/unselected이며 reason은 2,000자까지다. 시간이 미측정이면 비교값은 null이지 0초가 아니다. 이 자료는 user_timer_and_self_report로 명시하며 자동 실행으로 얻은 정확도 점수로 해석하지 않는다.

## 6.12 인수인계·첨부 계약

| 필드 | 제약 |
|---|---|
| title | 필수 1~100자 |
| purpose | 필수 1~3,000자 |
| progress | 필수 1~6,000자 |
| remaining | 필수 1~6,000자 |
| prompt | 선택 0~20,000자 |
| references | 최대 20개, 각 1~2,048자, 한 줄 경로 또는 http/https |
| revision | 변경 시 현재 양의 정수 |
| username | 공유 대상의 같은 서버 계정 ID |
| attach.name | 경로 문자가 없는 1~180자 파일명 |
| attach.data | 빈 파일이 아닌 Base64, 원본 최대 5MiB |

작업 생성 시 draft 상태와 revision 1을 저장한다. 변경마다 현재 버전을 확인하고 새 이력과 revision을 기록한다. 계정당 만든 인수인계 100개, 보통 200개 버전 상한이 있고 완료 동작은 버전 상한 예외다. 목록은 작성하거나 현재 받은 자료를 최대 200개 반환한다.

현재 첨부는 10개, 이전 이력에 남은 BLOB을 포함한 작업당 총량은 20MiB다. detach가 과거 버전의 원본까지 즉시 삭제하는 것은 아니다. GET files는 revision query가 필요하며 해당 버전의 첨부 목록과 현재 계정 권한을 모두 검사한다. 수신자는 공유 시작 revision 이전의 자료를 읽지 못하고, 수신자 변경 후 이전 대상의 접근도 유지되지 않는다.

view=1이면 허용된 PDF·이미지·텍스트의 제한된 미리보기를 제공하고 그 외는 attachment로 내려보낸다. 응답은 no-store·nosniff·sandbox CSP·same-origin CORP를 사용한다. HTML/SVG는 실행 문서가 아닌 일반 텍스트로 분류한다. 파일 원본이 악성이지 않음을 보장하는 바이러스 검사 API는 아니다.

## 6.13 업무 프롬프트 프로젝트 스키마

| project 핵심 필드 | 제약·의미 |
|---|---|
| schema_version, id, title | 현재 schema_version=1, 생성한 프로젝트 ID·제목 |
| raw_description, example_output | 업무 설명·기대 출력 예시 |
| requirements | 목적·변수·필수 규칙·표현 선호·출력 계약·질문 |
| requirements_revision | 요구사항의 현재 revision |
| confirmed_requirements_revision | 사용자가 확인한 revision 또는 null |
| artifact | 조립된 지침과 해당 revision 또는 null |
| runs | 시험 실행 기록; API 수신 시 최근 6개로 유지 |
| check_set | 준비된 검사 묶음 ID 또는 null |

출력 계약 fields는 name·type·required·description을 갖는다. name은 영문 소문자/밑줄로 시작하는 최대 40자의 소문자·숫자·밑줄이며 필드 이름이 중복되면 거절한다. type은 string·number·integer·boolean·array·object다. array는 item_type 또는 한 단계 item_fields 중 하나만 지정하고 min_items/max_items를 대조한다. object 내부의 임의 깊이 스키마 검사는 지원하지 않는다. 이 계약은 JSON Schema 표준 전체와 다르다.

목적·변수·규칙·선호에는 origin과 source_excerpt를 기록한다. origin은 extracted/suggested/user이며 AI가 제안한 내용을 사람이 확정한 요구사항과 구분한다. 업무 설명 최대 6,000자, 각 목록 최대 30개, 일반 설명 문자열 최대 1,000자, 지침 최대 12,000자 같은 validator 상한이 적용된다.

status·resolve·confirm·build는 반환된 project를 화면이 관리하는 경로다. 구조화·시험·AI 추천에는 실제 호출이 가능하며 서버 저장 여부와 별개다. 추천은 코드 규칙으로도 가능하지만 LIVE에서 모델 추천이 추가된다. 제안 시험은 기존 지침 1회와 시험 가능한 후보 수를 합산해 시작 전 남은 호출량을 확인한다.

apply-suggestions는 system_prompt와 touches_rules를 반환한다. allowRuleChanges 없이 보호된 필수 규칙을 변경하는 제안을 적용하지 못한다. trial-suggestions는 baseline과 results를 반환하며 이를 자동 채택이나 저장 명령으로 해석하지 않는다. export는 ZIP Base64와 파일명을 반환하고 includeData는 명시적으로 자료 포함 여부를 선택한다.

## 6.14 프로젝트 저장·버전·권한

| 역할 | 열기·과거 버전 | 새 버전·복원·draft | 공유 관리·삭제 |
|---|---|---|---|
| owner | 가능 | 가능 | 가능 |
| editor | 가능 | 가능 | 불가 |
| viewer | 가능 | 원본 수정 불가; 명시 저장은 자기 사본 | 불가 |
| 접근 없음 | 404 | 자기 사본 저장 규칙 외 원본 접근 불가 | 불가 |

목록은 projects, 상세는 id·role·owner·project·versions·draft를 반환하고 owner에게 members를 추가한다. 명시 저장은 version·copied와 overview를 반환한다. 복원은 과거 버전의 사본을 새 번호로 추가하고 과거 버전을 덮어쓰지 않는다. 자동 draft는 saved_at을 반환하며 새 버전이 아니다.

기본 상한은 소유 프로젝트 200개, 프로젝트당 버전 50개, 공유 인원 20개, 버전 라벨 60자, 소유 저장 자료와 자기 draft 총 20,000,000자다. DB 파일의 byte 크기 상한과 문자 수 한도는 다르다. 공유 입력 role은 viewer/editor다. 접근 불가 자료는 404, 읽기 권한은 있으나 동작 권한이 없으면 403으로 구분한다.

## 6.15 주요 요청·응답 예시 8종

아래는 계약 설명용 합성 입력이다. 실제 계정·세션 ID·원문 자료를 공개하지 않는다. 생략한 응답 필드는 앞의 스키마와 원자료를 따른다. 실행한 HTTP 결과를 캡처한 것이 아니다.

### 예시 1 — 코딩 지침 직접 조립

| 구분 | 값 |
|---|---|
| 요청 | POST /api/coding-instructions/preview |
| profile.language / framework | TypeScript / React |
| profile.preferences | explanation=brief, comments=essential, structure=modular, output=complete |
| profile.extra | 빈 문자열 |
| 응답 200 | draft.profile은 검증한 선택, draft.prompt는 네 조건과 항상 지킬 것 문구 |
| 확인점 | 모델 호출·기능 코드 생성 없이 지침만 조립 |

### 예시 2 — 요약 조건 충돌

| 구분 | 값 |
|---|---|
| 요청 | POST /api/summary-contract |
| domainKey / profile | summarization / length=short, extractiveness=fully |
| sourceText | “The team agreed. Work starts Monday. Review is on Friday.” |
| requiredSentences | 위의 서로 다른 완전한 문장 3개 |
| resolution | 생략 |
| 응답 200 | status=needs_resolution, conflict, prompts={}, task_requests={} |
| 후속 | 같은 입력에 resolution=expand를 주면 분량 조건을 늘린 ready 요청을 조립 |

### 예시 3 — 보관함 revision 충돌

| 구분 | 값 |
|---|---|
| 요청 | POST /api/preferences/{내항목ID}/update |
| 입력 | revision=1, title·domainKey·prompt·note |
| 전제 | 다른 창에서 현재 revision을 2로 수정함 |
| 응답 409 | 다른 창에서 수정되었다는 error |
| 확인점 | 원래 입력을 복사해 보존하고 최신 항목을 다시 읽음; 서버는 revision 2를 덮어쓰지 않음 |

### 예시 4 — 새 코딩 팀의 작업용 조합

| 구분 | 값 |
|---|---|
| 요청 | POST /api/coding-work/resolve |
| 입력 | profile=개인 네 조건, teamSelection.code=팀코드, revision=현재 팀 버전 |
| 다른 항목 | 개인 compact, 팀 modular인 structure만 다름 |
| teamSelection.choices | structure=team |
| 응답 200 | draft.profile.preferences.structure=modular, team_context, snapshot |
| 후속 저장 | snapshot과 같은 입력·새 title로 /api/coding-work/save; 원래 개인 지침 유지 |

### 예시 5 — 인수인계 이어받기

| 구분 | 값 |
|---|---|
| 요청 | POST /api/handoffs/{작업ID}/claim |
| 입력·로그인 | revision=4, 지정 수신자 쿠키 |
| 전제 | 현재 상태 shared, 현재 revision=4 |
| 응답 200 | handoff.status=active, revision=5, 수신자 can_edit=true |
| 예외 | 다른 계정이면 조회권한 또는 동작권한 오류; 오래된 revision이면 409 |

### 예시 6 — 버전별 첨부 열기

| 구분 | 값 |
|---|---|
| 요청 | GET /api/handoffs/{작업ID}/files/{파일ID}?revision=5&view=1 |
| 전제 | 현재 접근 가능한 계정, 5번 버전의 첨부 목록에 파일 존재 |
| 응답 200 | 허용 MIME 바이너리·Content-Disposition 및 보안 헤더 |
| 예외 | 공유 전 버전·그 버전에 없는 파일·권한 회수는 404 등으로 거절 |
| 확인점 | 링크를 안다는 사실만으로 자료 접근권한이 생기지 않음 |

### 예시 7 — GEPA 접수와 복구

| 구분 | 값 |
|---|---|
| 요청 | POST /api/coding-instructions/optimizations |
| 입력 | 지원 환경 profile, 서버 preview와 같은 originalPrompt |
| 전제 | 로그인·실제 모드·모델·도구 준비·사용량 여유 |
| 응답 202 | job.id, status=running, stage |
| 상태 조회 | GET /api/coding-instructions/optimizations/{jobId} |
| 재시작 | 중단된 running은 error로 복구, 같은 유료 요청을 자동 실행하지 않음 |

### 예시 8 — 사용자 작업 측정

| 구분 | 값 |
|---|---|
| 요청 | POST /api/coding-work/trials/{id}/result |
| 입력 | revision, arm=selected, outcome=pass, evidence=직접 실행한 검사 근거 |
| 테스트 수 | passed_tests=5, total_tests=5 |
| 응답 200 | trial.arms.selected와 comparison 갱신 |
| 예외 | pass인데 4/5이면 400; 실행 중 타이머가 있으면 먼저 pause 필요 |
| 확인점 | 사용자가 입력한 검사 기록이며 서버 자동 실행 결과가 아님 |

## 6.16 외부 시스템과 연계 경계

| 외부 대상 | 실제 연결 방식 | 데이터와 책임 |
|---|---|---|
| 모델 공급자 | 서버의 LiteLLM/GEPA 호출 | 지침·작업 입력 전송 가능; 명시 실행·캐시·한도 확인 |
| ChatGPT·Claude 등 사용자의 AI | 사용자가 지침을 복사해 붙여 넣음 | 제품이 해당 서비스 계정이나 대화를 자동 제어하지 않음 |
| Codex·Claude Code·Copilot·Cursor 지침 파일 | 파일 내용·차이 미리 보기 및 다운로드 | 실제 저장소 적용·도구 인식 여부는 사용자가 확인 |
| 팀 초대·인수인계 링크 | 같은 앱의 URL과 계정 권한 | URL만으로 비공개 자료 권한을 부여하지 않음 |
| HTTP 자료 링크 | 인수인계 references에 문자열 보관 | 서버가 외부 자료를 자동 수집·실행하지 않음 |
| 첨부 파일 | Base64 업로드·BLOB 저장·제한 열기 | 파일 크기·현재 권한·버전별 접근을 서버가 확인 |
| 연구 보조 에이전트 | 별도 benchmark 작업의 첫 응답 파일 | 운영 API 자동 무료 모드가 아니며 Codex 사용량 소비 |

## 6.17 명세 유지와 미해결 구현 차이

이번 명세는 구현된 계약을 기술하며 개선 희망을 현재 사실로 섞지 않는다. 비교 메모리 세션의 계정 소유권, 기존 원문 자동 절단, 프로세스별 잠금·실패 제한, 운영 프록시 가정, 프로젝트 버전 저장과 다른 자료의 revision 충돌 방식 차이는 추후 변경 때 명시적으로 검토해야 한다.

변경 시 api-inventory의 method/path, 요청 validator, 응답 필드, 인증·소유권, 사용량·저장 부작용을 함께 갱신한다. 메서드·정규 경로가 같더라도 입력 의미나 버전 정책이 바뀌면 호환성 변경이다. 이 문서 작성만으로 90개 endpoint에 대한 통합 테스트를 새로 통과한 것으로 보고하지 않는다.

