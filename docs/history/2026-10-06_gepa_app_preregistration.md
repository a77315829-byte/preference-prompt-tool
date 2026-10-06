# 사전등록: 실제 앱 조건에서 GEPA 의 추가 효과 (2026-10-06)

돌리기 전에 커밋한다. 결과를 본 뒤 기준을 바꾸지 않는다.

## 왜

`gepa_seed_conditions` 는 앱과 모델·시작 프롬프트가 달라 GEPA 를 남길지 뺄지 판단할 근거가
못 됐다 (`2026-10-06_review_response.md`). 이번에는 **앱이 실제로 부르는 함수를 그대로** 쓴다.

## 설계

- 도메인: `domains/summarization.yaml` (영어 MACSum - 사람 정답 요약이 있는 유일한 도메인).
- 페르소나: `heldout_comparison.pick_personas(30)` 과 같은 30명. 학습 문서 X 와 채점 문서 Y 가
  다르다 (test 분할, 문서 중복 없음). 지난 30명 실험과 사람·문서가 같아 이어 볼 수 있다.
- 선호 학습: `service.start_session` / `submit_choice` (앱의 선택기 - 양 끝부터, 같은 질문 반복
  없음). 후보 생성 `openai/gpt-4o-mini`. 페르소나의 선택은 `persona.choose`(legacy-a).
- 조건 두 개 (같은 학습 결과에서 갈린다):
  - **assembled**: `service.final_prompt(..., language="en")` - 앱이 결과 화면에 보여 주는 프롬프트.
  - **app_gepa**: `service.optimize(state, language="en")` - 앱의 "선호 기준으로 최적화" 버튼과 같은
    경로 (시작 = 위 프롬프트, 후보 평가 gpt-4o-mini, 성찰 `service.REFLECTION_MODEL` =
    gpt-5.6-luna, 예산 20회, 평가 입력 = 도메인 example_sources, 원문 누출 후보 제외).
- 적용: 두 프롬프트를 Y 원문에 `generate_with_prompt(..., gpt-4o-mini)` 로 적용 (온도 미지정 -
  지난 30명 실험과 같다).

## 지표

1. **주 지표 - ROUGE-L** (Y 의 사람 정답 요약 대비). 최적화에 쓰이지 않은 독립 지표 (절대 규칙 7).
2. 보조 - checks 점수 (페르소나의 **실제** 축값 대비). GEPA 는 **추정한** 축값으로 최적화하므로
   추정이 맞은 사람에서는 최적화한 지표와 사실상 같다. 그렇게 적어서 보고한다.
3. 보조 - 출력 길이 비율, GEPA 가 프롬프트를 바꾼 사람 수, 실제 비용.

## 판정 (미리 정한다)

- 30명 페어드, 양측 부호검정 (`experiments/result_statistics.sign_test_p`), 동점 제외.
- **"GEPA 가 추가 효과가 있다"**: ROUGE-L 에서 app_gepa 승 > 패 이고 p < 0.05.
- **"GEPA 가 해롭다"**: ROUGE-L 에서 패 > 승 이고 p < 0.05.
- 그 밖은 **"추가 효과 미확인"** - 앱 동작을 바꾸는 근거로 쓰지 않는다 (규칙 11).
- GEPA 가 프롬프트를 바꾼 사람이 15명 미만이면, 비교의 상당 부분이 "바꾸지 않음"을 잰 것이라고
  함께 적는다.
- checks 는 판정에 쓰지 않는다 (최적화한 지표).

## 비용

먼저 2명으로 단가를 잰다. 실제 청구 상한 $2 (litellm 콜백으로 합산, 넘으면 중단하고 그때까지
결과를 저장). 측정값 기준 GEPA 1회 약 $0.006 (`experiments/results/gepa_cost.json`).

## 하지 않는 것

- 다른 도메인·한국어 (사람 정답이 없다 - 규칙 8).
- 사람 참여자 평가 (별도 단계).
