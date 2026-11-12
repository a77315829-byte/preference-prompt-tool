# 5. 구성요소 및 내부 인터페이스 설계

이 장은 2026-11-12 로컬 구현을 기준으로 작성했다. 클래스가 실제 존재하는 경우와 함수 모듈을 구분한다. 서비스 전체를 하나의 거대한 클래스나 아직 없는 REST 프레임워크로 표현하지 않는다. HTTP 계층은 Python 표준 라이브러리 `BaseHTTPRequestHandler`와 `ThreadingHTTPServer`이며, 프론트는 React 컴포넌트와 함수로 구성된다.

## 5.1 계층과 책임 경계

| 계층 | 실제 구성 | 받는 자료 / 내보내는 자료 | 책임과 제외 범위 |
|---|---|---|---|
| 화면 | `frontend/src/app/App.jsx`, `features/*` | 사용자 입력 / JSON 요청, 복사·다운로드 | 진행 상태, 선택 확인, 로그인 복귀. DB 권한을 대신 판단하지 않는다. |
| HTTP | `api_server.ApiHandler` | HTTP / JSON·첨부 바이너리 | 경로 분기, 쿠키 인증, 입력 크기, 오류 상태, 사용량 차감. 학습 모델을 직접 구현하지 않는다. |
| 비교 서비스 | `service.py` | 원문·도메인·선택 이력 / `SessionState` | 엔진 재구성, 후보 확보, 종료 판단, 최종 지침·개선 연결. 계정 저장소가 아니다. |
| 도메인 독립 엔진 | `engine/` | `Domain`, 조합·비교 / 추정치·쌍·문구 | 축과 값의 일반 연산. 요약·코딩이라는 도메인 이름으로 분기하지 않는다. |
| 별도 제품 기능 | `summary_contracts_v2.py`, `summary_input_policy.py`, `coding_instructions.py`, `coding_elicitation.py` | 명시 조건 / 검증한 지침·선택 기록 | 현행 조건 확인·직접 설정 경로. 과거 summary_contracts.py와 실험 결과는 보존한다. |
| 영속 저장 | `Database`, 각 Store | 로그인 사용자 ID·명령 / 소유권 있는 자료 | 트랜잭션, revision, 이력, 상한. 쿠키 자체는 HTTP 계층에서 읽는다. |
| 외부 생성 | `engine.generator`, GEPA 관련 모듈 | 지침·작업 / 캐시된 모델 답변 | 서버가 고른 모델만 사용. 실제 호출 활성화·사용량 조건을 따른다. |
| 연구 검증 | `benchmarks/` | 고정 과제·첫 응답 / 검사·판정 | 제품 서버와 분리한 실험. 연구 실행 결과를 운영의 자동 기능으로 표현하지 않는다. |

`api_server.py`가 전역 `DB`, 저장소, 사용량 객체를 조립한다. 저장소 중 일부는 `lambda: DB`를 받으며 테스트에서 DB 교체가 가능하다. 이는 의존성 주입의 제한된 사용이며 별도 컨테이너 프레임워크가 있는 것은 아니다. 실제 서버를 import하면 환경 로드와 DB 객체 초기화가 수반될 수 있으므로 문서 분석에는 소스 읽기만 사용했다.

## 5.2 비교 서비스의 자료구조

| 실제 자료형 | 핵심 속성 | 생명주기와 의미 |
|---|---|---|
| `Candidate` | `id`, `text`, `combo` | 한 예시의 코드/텍스트와 생성 조건. 화면이 조건명을 강조해 선택을 유도하지 않도록 예시 내용 중심으로 보여 준다. |
| `PairView` | `pair_id`, `a`, `b` | 현재 응답 가능한 한 쌍. 제출 시 `pairId`를 대조해 이전 쌍의 중복 응답을 거절한다. |
| `AxisView` | `name`, `estimate`, `confidence`, `discriminated`, `total_rounds` | 진행·미정 항목 표시용. `fill`은 구분한 횟수의 비율이며 사람의 선호가 맞을 확률이 아니다. |
| `SessionState` | ID·도메인 경로·원문·모델·데모 여부, 이력·쌍·축, 완료 이유, 개선 상태·결과 | 직렬화 가능한 비교 세션. Estimator나 Selector 객체를 영속적으로 소유하지 않는다. |
| `Comparison` | `combo_a`, `combo_b`, `winner` | 엔진에 반영할 선택 단위. winner는 a·b·tie 중 하나다. |

`SessionState.history`는 두 조건 조합과 승자를 순서대로 보관한다. `round`와 `answered`는 이력에서 계산한다. `round_limit`은 원래 비교 상한을 보존하여 조기 종료 후 되돌릴 때 사용한다. `done`과 `completion_reason`을 같이 보내 상한 도달과 더 물을 쌍이 없음의 의미를 구별한다. `optimize_status`는 idle·running·done·error이며 비교의 완료 상태와 별도다.

### 서비스 연산과 불변 조건

| 연산 | 입력 / 출력 | 처리 순서·불변 조건 |
|---|---|---|
| `start_session` | 원문, 도메인, 데모·모델·상한 → SessionState | 도메인 로드, 초기 추정/선택기, 첫 쌍 생성. 실제 생성 실패의 데모 전환은 API 계층이 책임진다. |
| `_rebuild` | SessionState → Domain·Estimator·UncertaintySelector | 이력을 다시 재생하며 선택기의 난수 진행도 맞춘다. 이력과 다른 추정기를 재사용하지 않는다. |
| `submit_choice` | 상태·pair ID·a/b/tie → 새 상태 | 현재 쌍 대조, 이력 추가, 추정 재계산, 다음 쌍 또는 종료. 오래된 쌍은 `StaleChoiceError`다. |
| `undo_choice` | 현재 상태 → 이전 선택을 제거한 상태 | 이전 이력으로 복원하고 개선 표시를 정리한다. 캐시된 후보는 재사용한다. |
| `current_estimate` | 상태 → Domain·Estimator | 서비스 밖에서 최종 지침·팀 참여에 쓸 현재 추정치를 재구성한다. |
| `final_prompt` | Domain·Estimator·언어·템플릿 → 지침 문자열 | 신호가 없는 축을 숨은 기본 선택으로 확정하지 않는다. 언어별 도메인 문구를 조립한다. |
| `optimize` | 끝난 비교 상태·진행 콜백 → 지침 | 원본과 후보 평가, 원문 누출 검사, 개선 없으면 원본 유지. API의 스레드·할당량과 구분한다. |
| `exports_for` | 상태·지침·언어 → Export 목록 | 도구별 표현만 바꾼다. 저장소 파일을 자동 설치하거나 실행하지 않는다. |

근거: `service.py:80`, `service.py:129`, `service.py:173`, `service.py:367`, `service.py:407`, `service.py:454`, `service.py:515`, `service.py:743`.

## 5.3 도메인 모델과 추정·선택 알고리즘

| 클래스/모듈 | 구성과 연산 | 설계 의미 |
|---|---|---|
| `CheckSpec` | 검사 함수 지정·목표 | 도메인의 정량 기준을 엔진 바깥 검사 함수에 연결한다. |
| `AxisValue` | 축 값·문구·검사 | 값별 지침과 평가 조건을 함께 정의한다. |
| `Axis` | 이름·형식·값들, `instruction_for`, `check_for` | enum과 freeform을 구분한다. 자유 텍스트 축은 고정 값 선호 학습과 다르다. |
| `FinalPromptSpec` | 최종 지침 구성·번역·축 라벨 | 후보 생성 프롬프트와 재사용할 최종 지침을 구분한다. |
| `Domain` | 도메인 설정·축 목록, `axis` | YAML을 검증해 만든 자료형. UI나 계정 정보는 포함하지 않는다. |
| `Estimator` | 축별 utility·history, `update`, `has_signal`, `confidence` | Bradley–Terry 방식의 온라인 효용 갱신. 최상위 동률은 미정으로 다룬다. |
| `UncertaintySelector` | 다음 축·값 쌍, `next_pair` | 현재 추정 상태에 따라 비교를 정하고 UI 모드에서 이미 물은 쌍을 피한다. |
| `RandomSelector`, `SequentialAxisSelector` | 난수/순차 대조 선택 | 연구 대조 전략. 화면에서 모두 선택할 수 있는 메뉴를 의미하지 않는다. |

비교에서 다른 값인 축만 utility를 갱신한다. a가 이길 예측값은 두 utility 차이의 logistic 값이고 관측 목표는 a=1, b=0, tie=0.5다. 오차에 학습률을 곱해 두 값에 반대 방향으로 더한다. 따라서 tie는 언제나 아무 동작도 하지 않는 것이 아니라 이전 격차를 줄일 수 있다. 최상위 utility가 하나로 결정되었는지는 `TIE_TOLERANCE=1e-9`로 판단한다.

`confidence`는 softmax 분포의 정규화 엔트로피를 뒤집은 상대 집중도다. 보정된 확률이나 사람의 취향 정확도가 아니다. UI 비교 상한 8회는 제품의 부담 제한이며 이 수식만으로 8회 충분성을 증명하지 않는다. 새 코딩 4항목의 반복 선택 확인은 이 Estimator를 사용하는 경로가 아니다.

도메인 추가는 YAML의 축·값·문구·검사 지정, 도메인 검사 함수, 데모 예시, API 허용 경로·UI 안내를 함께 검토해야 한다. 엔진이 일반화되어 있다는 사실만으로 어떤 새 도메인이 자동으로 실행 검증되는 것은 아니다.

근거: `engine/domain_loader.py:13`, `engine/domain_loader.py:229`, `engine/estimator.py:27`, `engine/selector.py:89`.

## 5.4 생성·캐시와 도메인별 품질 경계

`engine.generator`는 `build_prompt`, `build_final_prompt`, `build_preference_section`, `build_template_prompt`로 문구를 구성한다. `generate`, `generate_all`, `generate_with_prompt`는 작업 원문·지침·모델 조건에 대응하는 캐시를 먼저 확인한다. 동일 키의 중복 요청은 키별 lock으로 묶는다. 캐시는 과제 데이터가 포함될 수 있는 비공개 실행 자료이며 공개 문서에 자동 복사하지 않는다.

| 생성 경로 | 무엇을 검증하는가 | 실패·미확인 처리 |
|---|---|---|
| 요약 후보 | 도메인의 문장 수·표현 조건 등 | 자동 형식 검사는 내용 보존·사실성 전체를 보장하지 않는다. |
| React 스타일 후보 | 준비된 스타일 검사와 후보 품질 | 기본 모델의 수정 후에도 실패하면 설정된 상위 모델 경로가 가능하다. 운영 비용·지연은 별도 측정 대상이다. |
| 무료 데모 | 준비된 규칙·합성 예시 | 요청한 임의 기능을 실제 생성한 것처럼 표시하지 않는다. `demo_reason`을 남긴다. |
| 저장 지침 새 작업 실행 | 선택한 지침과 새 작업으로 모델 생성 | 실패를 502로 반환하며 원래 지침·작업을 자동 변경하지 않는다. |
| GEPA | 후보 지침의 정해진 평가 | 좋은 후보가 없으면 원본 유지. 참고 점수와 별도 검증 결과를 나누어 표시한다. |

코딩 3축 스타일 후보와 코딩 4항목 지침은 서로 다른 제품 경로다. 한쪽의 캐시·선호 이력·검사 통과를 다른 쪽으로 옮겨 적용하지 않는다.

## 5.5 새 요약 조건 확인 모듈

`prepare_summary_contract(body)`는 domainKey·profile·sourceText·requiredSentences·resolution을 받는 순수 처리 경로다. API에서 호출하지만 모델과 DB를 호출하지 않는다. `source_sentences`가 표시 가능한 완전 문장을 추출하며 중복 선택·현재 원문 불일치를 거절한다. 선택 순서는 클릭 순서가 아니라 원문 순서로 정규화된다.

| 단계 | 입력·상태 | 산출물·조건 |
|---|---|---|
| 프로필 검증 | length, extractiveness, 선택 topic | 허용 값과 길이를 검증한 original_profile |
| 원문 검증 | 1~12,000자, 선택 문장 최대 8개 | available_sentences, required_sentences |
| 충돌 판정 | fully 발췌이며 선택 문장 상한 초과 또는 원문 문장 하한 부족 | 종류별 conflict와 needs_resolution; 지침과 작업 요청은 비움 |
| 해결 선택 | 상한: expand / rephrase / keep_limits; 하한: 가능한 shorten / rephrase | available_resolutions로 허용값 제한, 선택한 조건만 바꾼 effective_profile |
| 지침 조립 | 해결 조건·언어 | 원문 없는 prompts와 원문을 포함한 task_requests |

현행 함수는 summary_contracts_v2.py에 있다. 과거 모듈의 프로필·문장 검증을 재사용하되 v2 결과를 조립한다. 기본 resolution은 preserve다. 충돌에 맞지 않는 해결값은 400이다. expand/shorten은 원문과 선택 문장을 담을 수 있는 분량 단계로 조정하며 사용 가능한 원문 문장이 0개면 shorten을 제공하지 않는다. rephrase는 길이를 유지하며 extractiveness를 normal로 바꾼다. keep_limits는 기존 길이·발췌를 유지하고 일부 생략을 허용하므로 전체 보존으로 표현하지 않는다.

이 모듈의 ready는 규칙상 작업 요청을 만들 수 있다는 뜻이다. 생성될 요약이 옳다는 품질 판정이 아니다. 문장 속 대명사·인용에 필요한 맥락이나 의미상 압축 가능성은 별도 확인 대상이다.

## 5.6 코딩 직접 설정과 예시 비교

| 실제 함수/모듈 | 입력·출력 | 불변 조건 |
|---|---|---|
| `build_coding_instructions` | profile → profile·prompt | 언어·프레임워크와 네 키를 검증한 뒤 모델 없이 조립한다. |
| `build_coding_examples` | 검증한 profile → 기본 예시 묶음 | 언어별 준비 예시. 임의 작업의 생성 결과가 아니다. |
| `build_coding_elicitation` | profile → 과거 반복 비교 프로토콜 | 기존 버전 저장본 호환을 위한 경로다. |
| `build_adaptive_coding_elicitation` | profile → adaptive-v1 예시·상태 | 최대 8회, 1회 후 종료 가능. 엇갈림·미응답을 확인한다. |
| `validate_elicitation` | comparison·profile → 검증된 기록 | 버전·환경·예시 ID·연속 순서·응답·직접 확인 값 대조. |
| `inspect_answer` | profile·answer·isPatch → inspection | 정적 단서와 직접 확인 질문. 코드 실행·외부 모델 전송·자동 저장 없음. |

profile의 네 키는 explanation, comments, structure, output이다. 기본 문구는 기능 요구를 작성 선호보다 우선하고, 미지정 버전·정보는 질문하거나 가정을 표시하도록 한다. comparison 버전 1~4는 각 원래 규칙으로 읽으며 옛 기록을 최신 통계적 근거로 재해석하지 않는다. 현재 comparison에서 고른 값과 최종 preferences가 다르면 API는 재확인을 요구한다.

새 사용자의 UI는 미선택으로 시작하지만 examples API는 완성된 profile을 받는다. 프론트가 예시 요청용 값을 구성하는 절차와 사용자가 최종 확정한 선택은 구분해야 한다. 서버가 지원 언어 목록 밖의 문자열로 직접 지침을 조립하는 것과 해당 환경의 준비 예시·GEPA를 지원하는 것도 서로 다른 범위다.

## 5.7 인증·DB·할당량

| 실제 클래스 | 책임·주요 연산 | 보호하거나 유지하는 조건 |
|---|---|---|
| `Database` | SQLite 연결·migration | 사용자 자료, 계정·이력·상한을 하나의 앱 DB에서 관리한다. |
| `User` | id·username | 인증된 계정의 최소 자료. 비밀번호·토큰을 응답 payload에 포함하지 않는다. |
| `AuthService` | signup·login·user_for·logout·change_password·delete_account | 비밀번호 scrypt, 세션 토큰 SHA-256 저장. HTTP 쿠키 설정은 하지 않는다. |
| `FailureLimiter` | 실패 시각 보관·차단·정리 | 아이디·주소별 실패 제한. 메모리이므로 재시작 후 초기화된다. |
| `Quota` | 날짜·작업 종류·사용자별 사용량 | 전체/계정/익명 공용 상한. API 비용 금액 보장을 대신하지 않는다. |

로그인 세션 기본 수명은 14일이다. HTTP 쿠키는 HttpOnly·SameSite=Lax이며 Secure는 배포 설정에 따른다. 새 가입·로그인·비밀번호 변경·탈퇴의 입력 검증과 실패 상한은 인증 모듈이 담당한다. 비밀번호 변경은 기존 세션 정리 후 새 토큰을 반환한다.

비교용 메모리 세션은 로그인 세션과 다르다. `SESSIONS`는 서버 프로세스 메모리이며 기본 12시간·500개 제한과 정리 로직을 둔다. 이 경로에는 계정 소유권 검사가 없으므로 개인 보관함의 접근 통제 보장을 그대로 적용하면 안 된다. 문서의 운영 보완 과제로 남긴다.

## 5.8 개인 보관함과 조합 출처

`PersonalPromptStore`는 `list_for`, `get`, `create`, `update`, `delete`를 제공한다. 모든 조회는 owner_id를 사용하며 다른 사람의 항목은 존재하지 않는 것처럼 처리한다. 저장 상한은 계정당 100개, 제목 100자, 지침 20,000자, 메모 1,000자다. 수정·삭제는 예상 revision과 실제 revision을 트랜잭션 안에서 대조한다.

| 내부 자료 | 생성·검증 경로 | 이후 변경 시 처리 |
|---|---|---|
| `coding_profile_json` | 서버 조립 지침과 본문 일치 확인 후 저장 | 본문·분류 변경 시 hash 대조로 coding_profile_matches=false 표시 가능 |
| `provenance_json` | 개인/팀 조합·재조합 함수가 검증한 출처만 Store에 전달 | 당시 스냅샷 유지, 본문 변경 시 provenance_matches로 불일치 안내 |
| `optimization` | 서버 소유 GEPA 결과에서만 구성 | 원본 지침·보충 안내·평가 기록을 보존한 새 항목 |
| `team_context` | 같은 환경의 명시적 팀 기준 조합 | 개인 추가 메모·예시 이력을 팀 기본값으로 전송하지 않음 |
| `lineage` | 저장 ID·부모 revision 기반 목록 자료 | 삭제된 부모를 이름 추측으로 연결하지 않음 |

`preference_comparison.py`는 같은 도메인의 개인 지침과 기존 팀 추정을 비교하고, `compose_task_prompt`가 사용자가 고른 항목별 출처로 작업용 지침을 만든다. `saved_preference_remix.py`는 저장 당시 두 출처를 다시 선택하고, `saved_preference_restore.py`는 바뀐 항목 중 선택한 것만 이전 값·출처로 돌린다. 모두 기존 지침 덮어쓰기 대신 새로운 항목 저장으로 연결된다. 클라이언트가 임의로 보낸 출처 본문은 신뢰하지 않는다.

## 5.9 두 팀 모델의 구분

| 구분 | 기존 비교 팀 | 새 코딩 답변 방식 팀 |
|---|---|---|
| 담당 | `team.TeamStore`, `summarize` | `coding_team_guides.CodingTeamGuides` |
| 도메인 | 요약·React 스타일 등 비교 도메인 | `coding_profile` |
| 입력 | 끝난 비교의 선택 이력 | 팀장이 명시한 환경·네 항목 기본값·필수 규칙 |
| 결합 | 개인 추정의 동등 가중 집계 | 같은 환경에서 다른 항목마다 personal/team 직접 선택 |
| 변경 | 명시적 팀 참여·선택 추가 | 팀장만 revision 대조 후 기준 수정 |
| 출처 | 선택 이력·갈림 정도 | 팀 버전·개인/팀 값·규칙·선택 스냅샷 |

기존 팀의 다수 선택 집계를 팀 합의 또는 협업 효과로 표현하지 않는다. 새 팀의 필수 규칙은 작성 선호보다 우선하지만 작업 요구와 충돌하면 확인하도록 지침에 적는다. 이미 만든 새 팀의 개발 언어·프레임워크는 수정하지 못하며 바꾸려면 새 팀 기준을 만든다.

계정 팀은 팀장과 참여자가 자료를 읽으며, 비참여자는 초대가 필요한 최소 안내만 볼 수 있다. 새 참여에는 열린 초대가 필요하고 기본 7일 만료를 사용한다. 초대 닫기/재개는 팀장만 가능하다. 익명 체험 팀과 계정 팀의 공개 범위가 다르다.

## 5.10 인수인계와 첨부

`HandoffStore`는 create·get·list_for·change·history·file을 제공한다. 현재 계정이 작성자 또는 현재 수신자인지 `_load`에서 확인한다. `_public`은 각 상태의 can_edit·can_share·can_claim·can_complete·can_reopen을 계산하여 UI 버튼 표시의 근거를 보낸다. 서버가 change에서 같은 권한을 다시 확인하므로 UI를 우회해도 권한 검사 경로를 거친다.

| 동작 | 주체·전제 | 기록 |
|---|---|---|
| 생성 | 로그인한 작성자, 필수 본문 | draft, revision 1, created 이벤트 |
| 수정·첨부/제외 | 현재 편집 담당자, done 아님 | 본문/첨부 목록과 새 revision·이벤트 |
| 공유 | 대기 중 작성자; 수신 계정 삭제로 recipient_id가 NULL이면 복구 허용 | 수신자와 공유 시작 revision, shared |
| 이어받기 | 지정 수신자, shared | active, claim 이벤트 |
| 완료·재개 | 지정 수신자, active 또는 done | done 또는 active, 새 이벤트 |
| 과거 기록·파일 | 현재 접근권한과 공유 시작 revision | 해당 버전만 반환; 숨겨진 이전 자료 접근 거절 |

파일은 `handoff_files.upload_fields`에서 이름·Base64·크기를 검증하고 내용 선두 바이트·UTF-8 여부로 미리보기 MIME을 정한다. 원본은 SQLite BLOB이며 파일 이름을 OS 경로로 사용하지 않는다. detach는 현재 목록에서 제외하되 과거 버전에서 접근 가능한 원본은 보존한다. 따라서 과거 파일을 포함한 총량 20MiB도 검사한다. 서버가 파일의 악성 콘텐츠 전체를 판별하거나 무해함을 인증하는 것은 아니다.

## 5.11 GEPA 작업과 실제 작업 비교 기록

`CodingOptimizationJobs`는 계정별 background job을 관리한다. `start`는 서버 동시 2개·계정 1개 제한을 확인하고 사용량을 차감한 뒤 daemon thread를 시작한다. 같은 계정·같은 profile의 진행 중 요청은 기존 job을 반환한다. 공개 payload에서 owner·내부 시작시각·만료 내부값을 제거한다.

작업은 SQLite에 7일 보관한다. 서버 재시작으로 메모리에 없는 running 작업을 읽으면 error로 바꾸고 자동 재호출하지 않는다. 진행 콜백은 stage·model_calls·call_limit만 갱신한다. 완료 후 changed=true인 후보를 사용자가 채택하면 `save`가 서버 보유 결과로 새 보관 항목을 만든다. 이미 저장한 작업은 같은 saved_id 항목을 돌려주어 중복 생성을 막는다.

`CodingWorkTrials`는 모델 호출 없이 사용자의 실제 작업 비교를 기록한다. 생성 시 task·model·tool·context와 general/selected 지침을 고정한다. 타이머는 setup(준비·요청·응답 대기)과 edit(답변 수정·검사)의 두 단계다. 서버 시간으로 start/pause하며 계정당 동시에 하나만 진행된다. 검사 시간을 세 번째 타이머로 따로 재지는 않는다. pass/fail에는 근거 입력을 요구하고 미확인을 실패나 0초로 바꾸지 않는다. 기능 검사 수는 사용자 입력 기록이며 서버가 코드를 실행한 결과가 아니다. 실험실 보조 에이전트 검증과 이 사용자 측정 기능을 합산하지 않는다.

## 5.12 업무 프롬프트 작업 공간

| 모듈/클래스 | 책임 | 주요 불변 조건 |
|---|---|---|
| `models` | 프로젝트·요구사항·출력 계약 검증 | schema_version=1; 출력 계약은 제한된 자체 형식이며 전체 JSON Schema가 아니다. |
| `requirements` | 업무 설명을 요구사항으로 구조화 | AI 경로; 사용자 확인을 거쳐야 한다. 추출·제안·사용자 입력 출처를 구분한다. |
| `questions` | 미해결 질문 응답 적용 | 질문 ID·대상·응답을 검증하고 요구사항 상태를 갱신한다. |
| `builder` | 요구사항 확인과 지침 조립 | 확인 revision과 현재 revision의 일치를 검사한다. 오래된 확인으로 새 요구를 조립하지 않는다. |
| `runner` | 입력 대조, 생성, 출력 검사 | 모델 호출 전 잘못된 입력은 차단. 실행 기록과 검사 결과는 별개로 반환한다. |
| `suggest` | 코드 규칙/AI 개선 제안, 시험, 선택 적용 | 제안 보기·실제 적용을 분리. 제안 후보를 만든다고 원래 프로젝트가 덮어써지지 않는다. |
| `exports` | 지침 패키지 ZIP | includeData 명시 여부로 자료 포함을 구분한다. |
| `ProjectStore` | 저장·버전·공유·개인 draft | owner/editor/viewer 구분, 명시 저장만 새 버전, 복원도 새 버전이다. |

프로젝트는 화면이 JSON으로 보내고 서버가 매번 검증한다. 계정 저장은 별도 `/api/workspace/projects` 경로다. owner와 editor는 새 버전을 저장·복원할 수 있고 공유 관리·삭제는 owner만 가능하다. viewer가 저장하면 원본 수정 대신 자기 사본이 된다. 초안은 사용자마다 하나이므로 같은 프로젝트의 편집자끼리 작업 중 사본을 덮지 않는다.

## 5.13 프론트 컴포넌트 책임

| 컴포넌트/파일 | 상태·역할 | 협력 대상 |
|---|---|---|
| `App.jsx` | activeFlow, 선택 분류, 로그인 복귀, 초대·인수인계 URL, 위험 이동 확인 | 상위 메뉴와 feature 연결, logout 시 계정 초안 제거 |
| `ComparisonSection` | 원문·A/B·결과·언어 전환·기존 팀 연결 | 비교 API, SummaryContractPanel |
| `SummaryContractPanel` | 보존 문장·충돌·해결·재확인 | summary-contract API, 작업용/재사용 복사 분리 |
| `CodingInstructionsSection` | 환경→선택→확인·완성, 직접/예시 전환 | 환경·선호 카드, 예시 비교, 지침 preview |
| `CodingExampleComparison` | 선택 표시 후 다음, 종료·보류·기록 | repeatedComparison 함수, 서버 예시 |
| `CodingSignalSummary` | 한 번 선택·반복 일치·엇갈림·미응답 | 비교 결과와 직접 확인 화면 |
| `CodingOptimizationPanel` | 실행 가능 환경·시작·폴링·최근 작업·채택 | optimization API, Breakdown·AnswerReview |
| `CodingWorkflowPanel` | 팀 기준·내보내기·작업 비교 | CodingTeamPanel·CodingExportPanel·CodingTrialPanel |
| `PreferencesSection` | 목록·상세·수정·재사용 | 저장 API, TeamPreferenceComparison·Lineage |
| `TaskPreferenceMixer` | 항목별 개인/팀 선택·미리 보기 | compose-task, save-task |
| `RemixSavedPreferencePanel` | 저장한 두 출처 재선택 | remix-preview/save |
| `RestoreComparedPreferencePanel` | 바뀐 항목의 선택적 되돌림 | restore-preview/save |
| `TeamsSection` | 팀 생성·참여·초대·기준 표시 | 기존 팀 API 또는 새 코딩 팀 진입 |
| `HandoffsSection` | 작성·수신 작업·상태·버전·계정 지정 | HandoffFields·HandoffAttachments·handoffApi |
| `TemplateLibrarySection` | 분류·템플릿 보기·복사·비교 진입 | 비교 지원 여부, 요청 점검·작업 공간 진입 |
| `PromptWorkspaceSection` | 요구사항·계약·확인·조립·시험·저장 | ContractEditor·SuggestionPanel·CompareView |
| `PromptPolishSection` | 구조 점검과 명시 AI 다듬기 | checklist 경로와 polish 경로 분리 |
| `draftCache.js` | 계정별 sessionStorage·메모리 24시간 초안 | 메뉴 이동 복구·로그아웃 제거; 서버 저장 아님 |

프론트 API 래퍼는 응답 오류를 화면에 전달하고 서버 상태를 갱신한다. UI에서 비활성화된 버튼만으로 접근 통제를 보장하지 않는다. 현재 컴포넌트 분리를 전체 상태 관리 프레임워크나 전용 클라이언트 라우터의 도입으로 설명하지 않는다.

## 5.14 변경 영향과 확장 지점

| 변경 대상 | 함께 검토할 것 | 회귀 위험 |
|---|---|---|
| 선호 축·문구 | YAML, 검사, 데모, 최종 조립, 저장본 해석, 실험 루브릭 | 과거 기록 의미 변경·지시와 평가 불일치 |
| 직접 코딩 선택 | PREFERENCES, UI options, 비교 버전, 팀 조합, 저장 hash | 미정 값을 기본값으로 확정·다른 환경 출처 혼합 |
| API payload | 핸들러, validator, feature wrapper, 오류 UI | 저장 revision 누락·초안 복구 불능 |
| 저장 구조 | migration, FK, Store 트랜잭션, 삭제/권한 검사 | 기존 자료 손실·타 계정 노출 |
| GEPA 지원 환경 | 환경 등록, 준비·선택·최종 과제, 정적 평가 범위, UI 활성화 | 지원 선언이 실행 정확도 보장으로 오인 |
| 공개 문서 | 요구사항, 그림, 이 API 명세, 결과·한계, source hash | 과거 결과로 현재 기능 전체를 검증했다고 오인 |

이 장의 클래스·함수 목록은 전체 소스 파일의 모든 private helper를 열거한 API reference가 아니라 유지보수에 필요한 주요 책임과 협력 관계다. HTTP의 실제 지원 경로 전체와 입력·응답 계약은 다음 API 명세 및 `api-inventory.json`에서 별도로 추적한다.
