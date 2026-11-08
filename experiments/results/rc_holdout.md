# 요청 대조 규칙 비교 (holdout_v3) — 확증(판정에 쓴다)

- 생성: 2026-11-04T01:19:45.321903+00:00 · 모드 `execute` · 모델 `openai/gpt-4o-mini` · 반복 3 · temperature 0.7
- 추가 규칙: 코드를 내기 전에 개발 요청에 따옴표로 적힌 화면 문구, 버튼 글자, 표시 형식을 하나씩 대조하라. 글자를 바꾸거나 덧붙이지 말고, 요청에 없는 라이브러리(예: styled-components)를 쓰지 마라.

| 조건 | 출력 | 축 검사 통과율 | 기능 통과율 | 기능 미확인 |
|---|---|---|---|---|
| none | 60 | 0.4444 | None | None |
| rule_based | 60 | 0.6778 | None | None |
| request_check | 60 | 0.6833 | None | None |

| 짝 | 단위 | 축 검사 차이 [95%] | 기능 차이 [95%] |
|---|---|---|---|
| request_check-rule_based | 60 | 0.0056 (-0.05, 0.0611) | None None |
| rule_based-none | 60 | 0.2333 (0.1667, 0.3) | None None |

- 사전등록 기준: {"functional_gain": null, "style_non_inferior": true} → 전부 충족: `None`
- (보고용) 기본 조립본 기능 저하 재현: `None`
- 사용량(공급자 보고, 청구서 아님): {"generation_requests": 13, "input_tokens": 10586, "output_tokens": 5233, "unknown_usage_requests": 0, "elapsed_seconds": 68.44}
- 정적 축 검사와 과제별 고정 시나리오는 기능 동일성이나 사용자 만족을 입증하지 않는다. 과제·프로필 단위의 작은 차이는 결론으로 쓰지 않는다 (절대 규칙 11).
