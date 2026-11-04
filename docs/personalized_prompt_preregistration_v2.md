# AI 프롬프트 개선 단계 — 2차 실행 전 판단 기준 (2026-11-03)

1차 사전등록(`docs/personalized_prompt_preregistration.md`)은 기준 미충족이었다. 개선 단계를 **한 가지만 바꿔**
새 holdout 에서 다시 잰다. 이 문서는 **결과를 보기 전에** 커밋한다. 결과가 나온 뒤 기준을 바꾸지 않는다.
바꿔야 하면 문서 끝 변경 기록에 이유와 함께 적고, 바꾼 기준으로 낸 결과는 확증이 아니라 탐색으로 보고한다.

## 묻는 것

1차와 같다. 같은 가상 사용자의 선택 이력에서, AI 가 근거 있는 선호 줄만 다시 쓴 프롬프트 (c) 가 규칙 기반
조립본 (b) 보다 **목표 선호를 더 잘 따르게 하면서 기능은 해치지 않는가.** (a) 프롬프트 없음은 조작 확인이다.

## 1차와 달라진 것 (전부)

| 항목 | 1차 | 2차 | 이유 |
|---|---|---|---|
| 개선 단계 모델 | `openai/gpt-4o-mini` (생성과 같음) | **`openai/gpt-5.6-luna`** (`service.REFLECTION_MODEL` 기본값) | CLAUDE.md 스택 절의 원래 의도("성찰 모델만 강한 모델"). 1차 결과를 본 뒤 고른 가설이다 |
| holdout 과제 | v1~v4 보류 5과제 | **v5 새 5과제** (`tab_switch`, `char_counter`, `star_rating`, `like_toggle`, `temperature_convert`) | 1차 holdout 은 결과를 본 데이터다 |
| 개선본 검증 | `required_terms` | `required_terms`(+"억지로") + `weakening_markers` | 1차 이후 실제 화면 확인에서 구절 탈락을 보고 더했다(2026-11-03 기록 "후속 1~3"). 1차 결과 수치를 보고 고친 것은 아니다 |

후보 생성 모델(`openai/gpt-4o-mini`), 언어(`ko`), 프로필 4개(`PREREGISTERED_PROFILES`), 선택 이력 시뮬레이션,
temperature 0.7, holdout 반복 3회, `--fallback-as-base`, 지표, 판정 기준값, 부트스트랩(2,000회, 시드 0)은 1차와 같다.
개선 단계 시스템 프롬프트와 요청 형식(`agents/personalized_prompt.py`)도 바꾸지 않았다.

### 새 holdout 과제의 출처

v5 의 다섯 과제는 2차 설계 중 새로 썼고 생성을 한 번도 돌리지 않았다. 실행 시나리오(`runtime_check.cjs`)는
요청대로 쓴 정답 구현이 통과하고 한 군데만 틀린 변형이 실패하는지 먼저 확인했다
(`tests/test_runtime_scenarios_v5.py`, 5과제 모두 정답 통과·변형 실패). 1차 holdout 보다 쉬운지 어려운지는
모른다 - 그래서 1차와 2차 수치를 서로 비교해 결론을 내지 않는다. 판정은 2차 안의 (c)−(b) 짝 비교로만 한다.

## 단계

1. **Pilot (판정하지 않음)** — calibration 4과제 × 4프로필 × 1회. 개선 적용률, 파일 추출률, 새 모델의 응답 형식을
   본다. 코드 결함(크래시, 추출 실패 등)을 고치면 holdout 전에 변경 기록에 적는다. **개선 단계의 문구·기준·
   임계값·모델은 pilot 결과를 보고 바꾸지 않는다.**
2. **확증** — holdout_v2 5과제 × 4프로필 × 3회. 개선 단계 응답은 pilot 과 같은 이력이라 캐시를 탄다(새 개선 호출
   0회 예상). `source_sha256` 이 pilot 결과와 같아야 한다. 다르면 이유를 적는다.

```bash
# 사전 확인 (호출 0회)
python -m experiments.personalized_prompt_comparison --preregistered-profiles --split holdout_v2 --repeats 3 \
    --temperature 0.7 --fallback-as-base --improvement-model openai/gpt-5.6-luna
# 1. pilot
python -m experiments.personalized_prompt_comparison --execute --preregistered-profiles --split calibration \
    --temperature 0.7 --fallback-as-base --improvement-model openai/gpt-5.6-luna --max-api-calls 52 \
    --output-name ppc2_pilot
# 원문 검토 (data/personalized_prompt_comparison_outputs/) 후 실행 검사, 호출 0회
python -m experiments.personalized_prompt_comparison --cached-only --behavior --reviewed-outputs \
    --preregistered-profiles --split calibration --temperature 0.7 --fallback-as-base \
    --improvement-model openai/gpt-5.6-luna --output-name ppc2_pilot_behavior
# 2. 확증 (같은 순서: 생성 → 검토 → 실행 검사)
python -m experiments.personalized_prompt_comparison --execute --preregistered-profiles --split holdout_v2 \
    --repeats 3 --temperature 0.7 --fallback-as-base --improvement-model openai/gpt-5.6-luna \
    --max-api-calls 184 --output-name ppc2_holdout
python -m experiments.personalized_prompt_comparison --cached-only --behavior --reviewed-outputs \
    --preregistered-profiles --split holdout_v2 --repeats 3 --temperature 0.7 --fallback-as-base \
    --improvement-model openai/gpt-5.6-luna --output-name ppc2_holdout_behavior
```

### 호출과 비용 (실행 전 추정, 청구액 아님)

| 단계 | 최악 요청 수 (상한) | 예상 생성 요청 | 예상 개선 요청 |
|---|---|---|---|
| pilot | 52 | 최대 36 ((a)·(b) 는 1차 pilot 캐시를 탈 수 있다) | 4 (`gpt-5.6-luna`) |
| 확증 | 184 | 135 | 0 (캐시) |

1차 실측 기준 생성 1회 ≈ 입력 690 / 출력 480 토큰. 잔액·청구 금액은 확인하지 않는다.

## 지표·판정 기준·누락 처리

1차 문서의 "지표", "판정 기준", "누락 처리" 절을 **그대로** 쓴다. 요약:

1. 스타일 이득: (c)−(b) 축 검사 통과율 평균 차이 ≥ **+0.10** 이고 95% 구간 하한 > 0.
2. 기능 비열등: (c)−(b) 기능 통과율 차이 ≥ **−0.05**. 실행하지 못한 출력은 분모에 남기고 통과로 세지 않는다.
3. 적용률: 개선 미적용 비율 ≤ **0.25**.

셋 다 만족할 때만 "개선 단계(2차 설정)를 켤 근거가 있다"로 적는다. 그때도 기본값 변경은 팀이 정한다 -
이 문서는 근거만 낸다. 조작 확인 (b)−(a) ≤ 0 이면 (c)−(b) 를 해석하지 않는다. 생성 오류 행은 한 번만 재시도한다.

## 이 결과가 말하지 않는 것

- 실제 사람의 선호, 임의 입력에 대한 기능 동일성, 사용자 만족, 다른 언어·도메인으로의 일반화.
- 기준을 넘어도 원인이 모델 교체인지 검증 강화인지는 가르지 못한다(둘 다 1차와 다르다). 검증 강화는 (c) 를 버리는
  방향으로만 작동하므로 스타일 이득을 만들지는 못한다고 보지만, 확인한 것은 아니다.
- 표본이 작다(확증 60단위). 넘지 못한 것은 "이 설계로 확인되지 않았다"로 적는다. 과제·프로필 단위의 작은 차이는
  결론으로 쓰지 않는다 (절대 규칙 11).

## 변경 기록

(없음 - pilot 뒤에도 코드·문구·기준을 바꾸지 않았다. pilot·holdout 결과의 `source_sha256` 이 같다.)
- 2026-11-04 (결과 확인 후, 해석 메모만): 실행 검사가 여러 파일로 나눈 답의 실행용 `App.tsx` 껍데기 때문에 진입 파일을
  못 골라 미확인으로 세던 결함을 찾아 고쳤다(32977ae). 저장된 출력을 고친 검사로 다시 채점한 탐색 결과는
  `experiments/results/ppc2_holdout_behavior_rescored.*` 와 `docs/history/2026-11-03_personalized_prompt_improvement.md`
  "정리와 실행 검사 재채점" 절에 있다. 결과 절의 확증 판정과 수치는 바꾸지 않는다.

## 결과 (2026-11-03)

확증(holdout_v2 5과제 × 4프로필 × 3회 = 60단위, `experiments/results/ppc2_holdout_behavior.*`):

| 기준 | 값 [95% 구간] | 기준 | 충족 |
|---|---|---|---|
| (c)−(b) 축 검사 통과율 | +0.0167 [-0.0444, 0.0722] | ≥ +0.10, 하한 > 0 | 아니오 |
| (c)−(b) 기능 통과율 | -0.05 [-0.1333, 0.0167] | ≥ −0.05 | 예 (경계값) |
| 개선 미적용 비율 | 0.0 | ≤ 0.25 | 예 |

**판정: 기준 미충족. 개선 단계는 끈 상태를 유지한다.** 개선 단계 모델을 강한 모델로 바꿔도, 이 설계에서 AI 개선이
기본 조립본보다 목표 선호를 더 잘 따르게 한다는 것은 확인되지 않았다. 1차(-0.0389)와 2차(+0.0167) 모두 구간이 0 을
포함한다 - 두 번 다 "차이를 확인하지 못했다"이지 "효과가 없다"는 아니다.

조작 확인: (b)−(a) 축 검사 통과율 +0.2778 [0.2222, 0.3333] — 기본 조립본은 프롬프트 없음보다 목표를 따르게 했다.
기능 통과율 (a) 0.5333, (b) 0.35, (c) 0.30. 실행하지 못한 출력 (a) 4, (b) 6, (c) 9개는 통과로 세지 않았다.

**판정 밖의 관찰 (탐색, 사전등록한 비교가 아니다)**:

- (b)−(a) 기능 통과율 -0.1833 [-0.3333, -0.05]. 이 holdout 에서는 기본 조립본이 프롬프트 없음보다 요청 동작을 덜 지켰고
  구간이 0 을 포함하지 않는다. 1차 holdout 에서는 -0.05 였다. 차이는 주로 `like_toggle`(통과 (a) 4/12 → (b) 0/12)과
  `temperature_convert`(8/12 → 1/12)에서 났다 - 예: 초기 표시를 "화씨 32°F" 대신 "32°F" 로 썼다. 원인(스타일 지시가
  요청 문구 준수를 밀어내는지)은 이 실험으로 가를 수 없다. 기본 조립본의 기능 영향은 따로 사전등록해 볼 질문이다.
- `char_counter` 는 세 조건 모두 0/12 였다. 모델들이 "20자를 넘으면 글자 수 대신 경고를 보여 준다"로 해석했고 시나리오는
  둘 다 보이기를 기대했다 - 요청 문구가 두 해석을 허용한 과제 결함이다. 결과를 본 뒤 과제를 빼지 않는다는 규칙대로 그대로
  두었다. 세 조건이 같은 단계에서 모두 실패해 짝 차이에는 0 으로 들어가고, 기능 통과율 수준은 그만큼 낮아졌다.
- pilot 에서 한 프로필(compact/theme/inferred)의 개선 응답이 최상위 형식 검증(`languages`)에서 실패해 fallback 이 됐다.
  실패 응답은 캐시하지 않으므로 holdout 실행에서 같은 이력으로 한 번 더 요청했고 그때는 통과했다. holdout 의 미적용 비율
  0.0 은 그 재요청을 포함한다. 응답 원문은 남기지 않아 실패 내용을 확인할 수 없다.

사용량(공급자 보고 토큰, 청구서 아님): pilot 생성 12 + 개선 4회(입력 14,483 / 출력 8,021), holdout 생성 135 + 개선 1회
(입력 96,416 / 출력 67,842). 합계 152회, 입력 110,899 / 출력 75,863 토큰. 잔액·청구 금액은 확인하지 않았다.
생성 코드(pilot 48 + holdout 180)는 실행 전에 import 와 위험 API 를 전수 검색하고 일부를 읽었다(React·react-dom·
설치되지 않은 styled-components 만 import, 파일·네트워크·프로세스 접근 없음).
