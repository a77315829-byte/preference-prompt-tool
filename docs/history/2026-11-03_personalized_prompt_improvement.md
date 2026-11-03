# 2026-11-03 실시간 모드 AI 프롬프트 개선 단계와 3조건 비교

## 무엇이 바뀌었나

선택이 끝나면 `service.complete_personalized_prompt` 가 최종 프롬프트를 한 번 확정하고
`SessionState.prompt_improvement["method"]` 에 방식을 남긴다.

| method | 언제 | 프롬프트 |
|---|---|---|
| `rule_based` | 데모(`reason: demo_mode`), 실제 모드인데 꺼 둠(`disabled`, 기본값), 근거 있는 선호 없음(`no_supported_preferences`) | 기본 조립본. 모델 호출 없음 |
| `ai_improved` | 실제 모드에서 응답이 검증을 통과 | 근거 있는 선호 줄만 바뀐 조립본 |
| `fallback` | 문맥 구성 실패(`context_unavailable`), 한도(`limit_reached`), 호출 실패(`api_error`), 검증 실패(`invalid_response` + `validation_error` 단계) | 기본 조립본과 글자까지 같다 |

- **근거**: 그 축 값이 갈린 비교에서 사용자가 그 값을 가진 쪽을 직접 고른 라운드. "비슷해요"는 근거가 아니다.
  모델 응답의 축·값·라운드가 근거 밖이면 전부 버리고 `fallback`.
- **보호 문구**: 모델은 선호 줄(`- 라벨: 지시문`)의 지시문 부분만 한 줄로 바꿀 수 있다. 역할·과제·
  "항상 지킬 것"(기능 우선, 요청에 없는 기능 금지, 접근성, 완성 코드)·출력 형식은 코드가 원문에서 복사한다.
  다시 쓴 줄에는 `domains/*.yaml` 의 `final_prompt.required_terms`(축 → 값 → 낱말)가 모두 남아야 한다.
  빠지면 `validation_error: weakened` 로 폴백한다. 낱말 보존은 최소한의 경계일 뿐 의미 보존을 증명하지 않는다.
- **켜고 끄기**: 실제 모드에서도 기본은 끔(`PPT_PROMPT_IMPROVEMENT=1` 로 켠다). 비교 스크립트는 `enabled=True` 로 강제한다.
- **비용 기록**: `calls`, `input_tokens`, `output_tokens`, `elapsed_seconds` 는 이번에 보낸 요청만 센다.
  캐시를 타면 0 이고 저장된 요청의 사용량은 `original_usage` 로 따로 둔다. 검증을 통과한 응답만 캐시한다.
- **한도**: 세션당 실제 요청 2회(`service.MAX_PROMPT_IMPROVEMENTS_PER_SESSION`, 이전 선택 수정 후에도 유지),
  하루 상한은 React 경로 `PPT_PROMPT_IMPROVEMENTS_PER_DAY`/`PPT_USER_PROMPT_IMPROVEMENTS_PER_DAY`(DB 영속),
  Streamlit 경로 `MAX_PROMPT_IMPROVEMENTS_PER_DAY`(메모리, GEPA 예산과 분리). 한도 차감은 실제 요청 직전에만.
- **저장**: `data/prompt_results/`(또는 `PPT_PROMPT_RESULTS_DIR`)에 이력·근거·방식·프롬프트를 남긴다.
  공급자 오류 문구는 남기지 않는다. 저장이 실패해도 결과 화면은 그대로(`record_saved: false`).
- **중복·수정**: 같은 쌍에 대한 늦은 완료 요청은 409. 개선 중에 "이전 선택 수정"이 들어오면 그 상태를 덮어쓰지 않는다.
  선택을 되돌리면 개선 결과는 지워진다.
- **GEPA 와의 관계**: GEPA 는 개선 단계를 다시 부르지 않고 화면에 보인 프롬프트(개선본 또는 기본 조립본)를
  시드로 쓴다. GEPA 자신의 후보는 보호 문구를 보존한다는 보장이 없다 - 이 변경 전과 같다.

## 3조건 비교 실행

```bash
python -m experiments.personalized_prompt_comparison                      # 사전 확인, 호출 0회
python -m experiments.personalized_prompt_comparison --execute --task-limit 1 --max-api-calls 4
```

- 조건: (a) 시스템 프롬프트 없음 (b) 기본 조립본 (c) AI 개선본. 같은 과제(`benchmarks/coding_ai_quality/v1.json`
  calibration), 같은 모델(기본 `openai/gpt-4o-mini`, 개선 단계도 같은 모델), temperature 0, 같은 검사.
- 선택 이력은 목표 선호(`--profile`, 기본 separated/theme/explicit)를 가진 가상 사용자가 데모 후보로 만든다.
- 검사: 도메인 YAML 이 축 값마다 지정한 함수(`file_structure`, `theme_usage`, `type_explicitness`)의 통과 여부와
  원 신호 수, `candidate_quality_issues` 개수.
- 결과: `experiments/results/personalized_prompt_comparison.{json,md}`. 원 출력은 저장하지 않는다(캐시에만 있다).
- `--max-api-calls` 는 최악의 경우(개선 1 + 과제 × 3)보다 작으면 실행을 거부한다.

## 2026-11-03 실측 (과제 1개, n=1)

| 조건 | 파일 구성 | 스타일 관리 | 타입 작성 | 파일/테마/타입 신호 |
|---|---|---|---|---|
| (a) 없음 | ❌ | ❌ | ✅ | 1 / 0 / 5 |
| (b) 기본 조립 | ✅ | ✅ | ❌ | 2 / 19 / 3 |
| (c) AI 개선 | ✅ | ❌ | ❌ | 2 / 0 / 4 |

- 첫 실행은 개선 응답이 검증에 걸려 `fallback` 이었고 (c)는 측정하지 않았다(생성 2회 + 개선 1회, 입력 1,926 / 출력
  1,301 토큰, 31.7초). 요청 형식을 축별 `current_instruction`·`allowed_rounds`·응답 틀로 명시한 뒤 두 번째 실행에서
  `ai_improved`(생성 1회 + 개선 1회, 입력 1,957 / 출력 662 토큰, 14.9초; 개선 단계만 1,284 / 181 토큰, 8.1초).
  두 실행 합계 새 요청 5회. 토큰은 공급자 보고값이고 청구서가 아니다. 잔액·청구 금액은 확인하지 않았다.
- AI 개선본은 세 선호 줄을 바꿔 쓴 수준이었고 "꼼꼼하게 명시하라"가 "명확히 명시하라"로 약해졌다.
- 이 한 사례에서 (c)는 (b)보다 스타일 관리 검사를 하나 덜 통과했다. 과제 1개·생성 1회라 결론이 아니다
  (절대 규칙 11). **AI 개선이 프롬프트를 낫게 만든다는 증거는 아직 없다.**
- 정적 검사 통과는 기능 동일성, 실행 가능성, 사용자 만족을 보여 주지 않는다.

## 독립 지표: 실행 검사 (3단계)

```bash
python -m experiments.personalized_prompt_comparison --cached-only \
    --ai-prompt-from experiments/results/personalized_prompt_comparison.json      # 호출 0회, 원문을 data/ 에 꺼냄
# data/personalized_prompt_comparison_outputs/*.md 를 읽고 검토한 뒤
python -m experiments.personalized_prompt_comparison --cached-only --behavior --reviewed-outputs \
    --ai-prompt-from experiments/results/personalized_prompt_comparison.json
```

- 스타일 검사·GEPA 와 다른 기준으로 `benchmarks/coding_ai_quality/evaluate_trial` 의 기존 실행 검사를 그대로 쓴다:
  tsc 타입 검사 → esbuild 번들 → jsdom 에서 과제의 고정 인수 시나리오. 셋 다 통과해야 "기능 통과(독립)".
- 생성 코드를 로컬 Node 에서 실행한다(보안 샌드박스 아님). `--reviewed-outputs` 없이는 거부한다(절대 규칙 9).
- 기존 추출기는 ```` ```typescript ```` 블록을 읽지 못해 그 표기만 ```` ```tsx ```` 로 바꾼다(`fence_normalized` 로 기록).
  그래도 파일을 확정하지 못하면 실패가 아니라 미확인(`functional_pass: null`)으로 남긴다.
- `--cached-only` 결과는 `experiments/results/personalized_prompt_comparison_cached.{json,md}` 에 따로 쓴다.
  `--ai-prompt-from` 은 이전 실행의 (c) 프롬프트를 재생한다 - 현재 검증(`weakened`)이라면 거부됐을 프롬프트다.

2026-11-03 결과 (위 실측의 같은 출력 3개, 새 호출 0회, 원문 검토 후 실행):

| 조건 | 타입 검사 | 빌드 | 시나리오(증가·증가·초기화) | 기능 통과 |
|---|---|---|---|---|
| (a) 없음 | ✅ | ✅ | 3/3 | ✅ |
| (b) 기본 조립 | ✅ (블록 표기 정규화) | ✅ | 3/3 | ✅ |
| (c) AI 개선 | ✅ | ✅ | 3/3 | ✅ |

- **독립 지표로는 세 조건의 차이가 없다.** 스타일 검사의 차이는 기능 차이를 동반하지 않았다.
- `counter_reset` 시나리오는 약하다(예: 첫 항목은 화면 어딘가에 `0` 이 있는지만 본다). 과제 1개·생성 1회다.

## 사전등록 (4단계)

확대 비교의 설계·지표·판정 기준을 `docs/personalized_prompt_preregistration.md` 에 결과 전에 고정했다.
스크립트에 여러 프로필(`--preregistered-profiles`), 반복(`--repeats`, 반복마다 캐시 폴더 분리), holdout 과제 모음
(`--split holdout`, v1~v4 의 보류 과제 5개), 서비스와 같은 폴백 처리(`--fallback-as-base`), 결과 파일 이름
(`--output-name`), 판정 기준의 기계적 계산(`summary.criteria`), 사용한 코드의 해시(`source_sha256`)를 더했다.
사전등록 커밋(`c182cd5`) 뒤에 실행했다.

## 확대 비교 결과 (5단계)

- pilot(calibration 4과제 × 4프로필, 판정 아님)과 확증(holdout 5과제 × 4프로필 × 3회)을 실행했다. 판정과 수치는
  `docs/personalized_prompt_preregistration.md` 의 "결과" 절. **기준 미충족 — 개선 단계는 꺼 둔다.**
- (c)−(b) 축 검사 통과율 -0.0389 [-0.0944, 0.0167], 기능 통과율 -0.0333 [-0.1333, 0.05].
  (b)−(a) 축 검사 통과율 0.2889 [0.2222, 0.3611].
- 새 API 요청(공급자 보고 토큰, 청구서 아님): pilot 1차 40회(생성 36 중 16 실패, 개선 4 중 1 실패; 입력 16,618 / 출력 12,587),
  재시도 17회(입력 13,057 / 출력 8,828), holdout 1차 135회(Timeout 1; 입력 94,053 / 출력 64,239), 재시도 1회(입력 849 / 출력 408).
  합계 193회, 입력 124,577 / 출력 86,062 토큰. 실패한 요청의 사용량은 보고되지 않아 합계에 없다. 잔액·청구 금액은
  확인하지 않았다. 실행 검사는 캐시 재생이라 호출 0회.
- 생성 코드(pilot 48 + holdout 180)는 실행 전에 import 와 위험 API(fs, child_process, process, 네트워크, eval, 동적 import,
  무한 반복)를 전수 검색하고 일부를 읽어 검토했다. 설치되지 않은 `styled-components`·`@emotion/react` 를 쓴 출력은
  빌드 실패로 셌다.

## 마무리 (6단계 이후)

- **GEPA 와 보호 규칙**: GEPA 성찰 모델은 프롬프트를 통째로 다시 써 "항상 지킬 것" 줄을 지울 수 있었다.
  고른 후보에서 시드에 있던 규칙 줄이 빠지면 그 줄만 YAML 원문 그대로 규칙 머리말 아래에 다시 붙인다
  (`service._restore_protected_rules`, 보고에 `rules_restored`). 빠진 후보를 버리는 방식은 GEPA 를 거의 항상 시드로
  되돌려 택하지 않았다. 규칙을 다시 붙인 프롬프트는 GEPA 가 점수를 낸 그 텍스트와 다르다 - 점수는 붙이기 전 기준이다.
- **팀 순서 흔들림**: `team.TeamStore` 가 `joined_at` 으로 정렬해, 재참여가 다른 초에 들어오면 순서가 바뀌어
  `test_team` 이 간헐 실패했다. upsert 가 유지하는 `rowid`(처음 참여한 순서)로 정렬하고, 시계를 주입한 재현 테스트를 더했다.
- **화면 확인**: Streamlit 결과 화면은 `AppTest` 로 세 방식(`rule_based`/`ai_improved`/`fallback`)의 표시 문구와
  보이는 프롬프트를 확인했다(테스트로 고정). React 결과 영역은 브라우저 없이 `react-dom/server` 렌더로 같은 세 경우의
  문구와 프롬프트를 확인했다 - 실제 브라우저 상호작용(복사 버튼, 언어 전환)은 보지 않았다.

## 남은 것

- 사전등록 비교에서 개선 단계를 켤 근거는 확인되지 않았다. 다시 시도하려면 개선 방식을 바꾸고 새 holdout 으로 새 사전등록을 해야 한다.
- 2026-11-03 후속: 위 실측의 "꼼꼼" 탈락은 `required_terms` 검사로 이제 폴백된다(저장된 결과로 오프라인 확인,
  새 호출 없음). 낱말을 지키면서 의미를 약하게 만드는 경우는 여전히 못 잡는다.

## 후속 1~3 (같은 날)

1. **React 화면 상호작용**: 이 컴퓨터에는 자동 조작 가능한 브라우저가 없다(Safari 원격 자동화는 시스템 설정 변경이라
   켜지 않았다). 대신 `ComparisonSection` 을 esbuild 로 묶어 jsdom 에 올리고 **실제 `api_server`** (임시 DB·기록 폴더)에
   붙여 클릭으로 끝까지 진행했다. 세 경우 모두 13개 확인 항목 통과: 시작 → 선택 3회 → 결과, 생성 방식 문구와 `<code>`,
   언어 전환(aria-pressed, 언어마다 다른 프롬프트), 복사 내용 = 화면 프롬프트, 언어 전환 시 복사 표시 초기화,
   "프롬프트 + 개발 요청 복사", 복사 실패 시 `role=alert` 안내, "마지막 선택 수정" 후 질문 복귀.
   - 데모(`PPT_LIVE=0`): `rule_based`, 호출 0회.
   - 실제 + 개선 켬(`PPT_PROMPT_IMPROVEMENT=1`): `ai_improved`, 개선 호출 1회(입력 1,897 / 출력 646 토큰, 11.7초).
     화면의 ko·en 프롬프트가 저장 기록의 개선본과 같고 기본 조립본과 다름을 대조했다. 후보 생성은 캐시를 탔다.
   - 실제 + 개선 상한 0: `fallback`(`limit_reached`), 호출 0회, 화면 프롬프트 = 기본 조립본(ko·en).
   - 실제 브라우저 엔진(레이아웃, 실제 클립보드 권한, 애니메이션)은 여전히 확인하지 않았다. 확인 스크립트는 저장소에 넣지 않았다.
2. **GEPA 점수**: 규칙 줄을 되살린 경우 그 프롬프트를 같은 평가 세트로 다시 재서 `final_score` 로 보고하고
   (`score_before_restore` 에 GEPA 점수), 다시 잰 점수가 시드 이하이면 시드를 유지한다. 평가 입력 수만큼 호출이 는다.
   실제 GEPA 1회(코딩, 315초)에서는 두 후보가 모두 원문 유출 검사에 걸려 시드가 유지돼(`leaky_skipped` 2,
   `rules_restored` 0) 이 경로는 실측으로 지나가지 않았다 - 단위 테스트로만 확인했다. 한국어 개발 요청에서 코딩 GEPA
   후보가 유출로 걸리는 빈도는 이 1회로 판단하지 않는다(절대 규칙 11).
3. **의미 약화**: 1의 실측 개선본이 역할별 파일 줄에서 "필요 없는 하위 컴포넌트와 타입 전용 파일을 억지로 만들지 말고"를
   지웠는데 검증을 통과했다. `required_terms` 에 "억지로"를 더했고, 원래 줄에 없던 완화 표현(`weakening_markers`:
   "가능하면", "if possible" 등)이 생기면 `weakened` 로 버린다. 한국어 "필요한 타입만" 줄은 원래 "가능하면·필요하면"을
   담고 있어 그 줄에서는 그 두 표현을 검사하지 못한다(테스트로 고정). 낱말 목록 검사라 바꿔 말한 약화는 여전히 못 잡는다.
