# AI 프롬프트 개선 단계 — 실행 전 판단 기준 (2026-11-03)

실시간 모드의 AI 프롬프트 개선(`PPT_PROMPT_IMPROVEMENT`, 현재 기본 끔)을 켤 근거가 있는지 잰다.
이 문서는 **결과를 보기 전에** 커밋한다. 결과가 나온 뒤 기준을 바꾸지 않는다. 바꿔야 하면 바꾼 이유와 함께
이 문서 끝의 변경 기록에 따로 적고, 바꾼 기준으로 낸 결과는 확증이 아니라 탐색으로 보고한다.

## 묻는 것

같은 가상 사용자의 선택 이력에서, AI 가 근거 있는 선호 줄만 다시 쓴 프롬프트 (c) 가 규칙 기반 조립본 (b) 보다
**목표 선호를 더 잘 따르게 하면서 기능은 해치지 않는가.** (a) 프롬프트 없음은 개인화 자체가 작동하는지 보는
조작 확인이다. 판정에는 쓰지 않는다.

## 이미 본 것 (정직하게 적는다)

`docs/history/2026-11-03_personalized_prompt_improvement.md` 의 탐색 실행 두 번:

- 과제 1개(`counter_reset`, calibration), 프로필 1개(separated/theme/explicit), temperature 0, 생성 1회.
- 축 검사 통과 (a) 1/3, (b) 2/3, (c) 1/3. 실행 검사는 셋 다 통과.
- 이 실행을 보고 개선 단계에 두 가지를 바꿨다: 요청 형식 명시(첫 실행이 검증 실패), `required_terms`
  낱말 보존 검사("꼼꼼" 탈락). 따라서 `counter_reset` 과 그 프로필은 **이미 본 데이터**다.
- 판정은 아래 holdout 과제에서만 한다. holdout 다섯 과제는 서비스 경로 A/B 생성 평가에 쓰였지만,
  개선 단계나 이 비교의 설계를 고치는 데에는 쓰지 않았다.

## 설계 (고정)

| 항목 | 값 |
|---|---|
| 모델 | `openai/gpt-4o-mini` — 생성과 개선 단계 모두 (서비스 후보 생성 기본값과 같다) |
| 언어 | `ko` 최종 프롬프트 |
| 프로필 (`PREREGISTERED_PROFILES`) | separated/theme/explicit, compact/direct/inferred, compact/theme/inferred, separated/direct/explicit — 각 축의 두 값이 두 번씩 목표가 된다 |
| 선택 이력 | 목표와 맞는 축이 더 많은 쪽을 고르는 가상 사용자, 데모 후보, 최대 8라운드. 네 프로필 모두 복원되고 세 축 모두 근거가 생기는 것을 실행 전에 확인했다 (3라운드에서 종료) |
| 조건 | (a) 시스템 프롬프트 없음 (b) 기본 조립본 (c) 개선본. 개선이 적용되지 않은 프로필은 서비스와 같게 (c)=(b) (`--fallback-as-base`) |
| temperature / 반복 | 0.7 / holdout 3회 (반복마다 캐시 폴더를 나눈다) |
| 분석 단위 | 프로필 × 과제 × 반복. (b)·(c) 는 같은 단위끼리 짝짓는다 |

### 단계

1. **Pilot (판정하지 않음)** — calibration 4과제 × 4프로필 × 1회. 파이프라인, 개선 적용률, 파일 추출률만 본다.
   여기서 코드 결함(크래시, 추출 실패 등)을 고치면 holdout 전에 변경 기록에 적는다. **개선 단계의 문구·기준·
   임계값은 pilot 결과를 보고 바꾸지 않는다.**
2. **확증** — holdout 5과제(`confirm_dialog`, `text_preview`, `password_visibility`, `faq_toggle`,
   `cart_quantity`) × 4프로필 × 3회. 개선 단계 응답은 pilot 과 같은 이력이라 캐시를 탄다(새 개선 호출 0회 예상).
   결과 파일의 `source_sha256` 이 pilot 결과와 같아야 한다. 다르면 다른 이유를 적는다.

```bash
# 사전 확인 (호출 0회): 계획과 최악 호출 수
python -m experiments.personalized_prompt_comparison --preregistered-profiles --split calibration \
    --temperature 0.7 --fallback-as-base
# 1. pilot
python -m experiments.personalized_prompt_comparison --execute --preregistered-profiles --split calibration \
    --temperature 0.7 --fallback-as-base --max-api-calls 52 --output-name ppc_pilot
# 원문 검토 (data/personalized_prompt_comparison_outputs/) 후 실행 검사, 호출 0회
python -m experiments.personalized_prompt_comparison --cached-only --behavior --reviewed-outputs \
    --preregistered-profiles --split calibration --temperature 0.7 --fallback-as-base --output-name ppc_pilot_behavior
# 2. 확증 (같은 순서: 생성 → 검토 → 실행 검사)
python -m experiments.personalized_prompt_comparison --execute --preregistered-profiles --split holdout \
    --repeats 3 --temperature 0.7 --fallback-as-base --max-api-calls 184 --output-name ppc_holdout
python -m experiments.personalized_prompt_comparison --cached-only --behavior --reviewed-outputs \
    --preregistered-profiles --split holdout --repeats 3 --temperature 0.7 --fallback-as-base \
    --output-name ppc_holdout_behavior
```

### 호출과 비용 (실행 전 추정, 청구액 아님)

| 단계 | 최악 요청 수 (상한) | 예상 생성 요청 | 예상 개선 요청 |
|---|---|---|---|
| pilot | 52 | 36 ((a) 는 프로필끼리 공유) | 4 |
| 확증 | 184 | 135 | 0 (캐시) |

탐색 실행 기준 생성 1회 ≈ 입력 650 / 출력 500 토큰. 합계 약 입력 11만 / 출력 9만 토큰 수준으로 예상한다.
공급자 보고 토큰은 결과 파일에 남기지만 청구서가 아니다. 실행 전에 팀이 범위를 승인한다.

## 지표

- **축 검사 통과율** (주 지표): 출력마다 목표 프로필 세 축의 지정 검사(`file_structure`, `theme_usage`,
  `type_explicitness`) 통과 비율. 세 축 전부 통과 비율도 함께 보고한다.
- **기능 통과율** (독립 지표, 절대 규칙 7): tsc 타입 검사 + esbuild 빌드 + 과제의 고정 jsdom 시나리오가 모두 통과한
  출력의 비율. 실행하지 못한 출력(추출 실패 등)은 **분모에 남기고 통과로 세지 않으며** 미확인 수를 따로 적는다.
  ```` ```typescript ```` 표기 정규화는 결과에 기록한다.
- **개선 미적용 비율**: 네 프로필 중 개선 단계가 `ai_improved` 가 아니었던 비율.
- 짝지은 차이 (c)−(b), (b)−(a) 의 평균과 95% 부트스트랩 구간 (단위 복원추출 2,000회, 시드 0).

## 판정 기준 (holdout 결과에만 적용)

세 가지를 **모두** 만족할 때만 "개선 단계를 켤 근거가 있다"로 적는다. 하나라도 아니면 끈 상태를 유지한다.

1. **스타일 이득**: (c)−(b) 축 검사 통과율 평균 차이 ≥ **+0.10** 이고 95% 구간 하한 > 0.
2. **기능 비열등**: (c)−(b) 기능 통과율 차이 ≥ **−0.05**.
3. **적용률**: 개선 미적용 비율 ≤ **0.25** (네 프로필 중 최대 1개).

값은 스크립트 상수(`MIN_STYLE_GAIN`, `MAX_FUNCTIONAL_DROP`, `MAX_FALLBACK_RATE`)와 같고 결과 파일의
`summary.criteria` 가 기계적으로 계산한다. 실행 검사를 돌리지 않았으면 판정은 `None` 이다.

**조작 확인 (판정 아님)**: (b)−(a) 축 검사 통과율 차이가 0 이하이면 "이 설계에서는 기본 조립본도 목표를 따르게
하지 못했다"로 적고, (c)−(b) 결과를 해석하지 않는다.

## 누락 처리

- 생성 오류 행은 같은 상한 안에서 같은 명령을 다시 실행해 한 번만 재시도한다(완료된 행은 캐시를 탄다).
  그래도 남은 누락은 조건별로 개수를 보고하고, 짝 비교에서는 두 조건이 다 있는 단위만 쓴다.
- 결과를 본 뒤 단위·과제를 빼지 않는다.

## 이 결과가 말하지 않는 것

- 실제 사람의 선호. 가상 사용자는 축 조합만 고른다.
- 임의 입력에 대한 기능 동일성. 실행 검사는 과제마다 정해진 시나리오만 본다.
- 사용자 만족, 가독성, 다른 모델·언어(`en`)·도메인으로의 일반화.
- 표본이 작다(확증 60단위, 프로필 4개). 기준을 넘지 못한 것은 "효과가 없다"가 아니라 "이 설계로 확인되지 않았다"로 적는다.
  과제·프로필 단위의 작은 차이는 결론으로 쓰지 않는다 (절대 규칙 11).

## 변경 기록

(결과를 본 뒤 바꾼 것이 있으면 날짜·이유·영향을 여기에 적는다.)
