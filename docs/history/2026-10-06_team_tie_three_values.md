# 2026-10-06 값이 3개인 축의 팀 동률 (0ef9702 기준)

## 결함

같은 날의 수정 3("팀 1:1 의견 충돌", 47277d7)은 값이 2개인 축에서만 맞았다. 판정
(`Estimator.has_signal`)이 "값들 사이에 차이가 있는가"였기 때문이다. 값이 3개 이상인 축에서
1:1 로 갈리면 1위 둘은 같고 아무도 고르지 않은 값만 낮아서, 차이는 있는데 1위는 정해지지 않았다.

재현 (summarization 의 `length` = short / normal / long, 두 사람이 short 와 normal 로 대칭으로 갈림):

- 합친 효용 `{'short': 1.3737, 'normal': 1.3737, 'long': 0.2526}`
- `team_value='short'` (YAML 정의 순서상 앞일 뿐), `tied=True`
- 팀 프롬프트에 `- 분량: 2문장 이내로 아주 짧게 요약하라.` 가 들어갔다
- 화면은 "지금 팀 프롬프트는 선호가 조금 더 기운 쪽인 short" 라고 보여 줬다 - 기운 쪽이 없다
- 3:3 이면 합친 효용의 차이가 ±4.4e-16 이고 부호가 팀원 순서를 따라, 팀 값이 순서에 따라
  short / normal 로 뒤집혔다

기존 테스트(`test_even_split_is_a_tie_not_undecided`)는 모든 축의 값이 2개인 coding 도메인으로만
쟀다. 값이 2개면 1위 동률이 곧 전부 동률이라 드러나지 않았다.

## 고친 것

- `has_signal` 은 **1위가 하나로 정해졌는가**를 본다. 1위와의 차이가 `TIE_TOLERANCE`(1e-9) 이하인
  값이 둘 이상이면 신호 없음이다. 허용 오차는 위 부동소수점 끝자리를 흡수하기 위해서다 - 학습으로
  생기는 차이는 학습률(0.5) 단위라 훨씬 크다.
- 그래서 같은 수로 갈린 축(1:1, 3:3, 대칭인 1:1:1)은 팀 값이 빈 문자열이고 팀 프롬프트에서 빠진다.
  화면 문구는 "의견이 정확히 반으로 갈려" 를 "의견이 같은 수로 갈려" 로 바꿨다 (세 갈래도 있다).
- 한쪽이 더 분명하게 고른 1:1 은 예전처럼 그쪽으로 기운다 (`tied=True`, 팀 값 있음).

`has_signal` 을 쓰는 다른 곳(개인 결과의 정하지 못한 축, 최적화 가능 여부, 채점에서 뺄 축,
`experiments/selector_tie_accuracy.py`)도 같은 판정을 따른다. 개인 추정에서 1위만 정확히 같아지는
일은 갱신 폭이 매번 달라 사실상 생기지 않으므로, 저장된 실험 결과는 바뀌지 않는다
(`tests/test_selector_tie_accuracy.py` 통과).

회귀 테스트: `tests/test_review_fixes.py` 의 3-1 절 4개, `tests/test_undecided_axes.py` 의
`test_has_signal_needs_a_single_top_value`. 고친 판정을 되돌리면 넷 다 실패한다 (한쪽이 기운 경우를
보는 `test_uneven_confidence_still_leans` 는 고치기 전후 모두 통과).
