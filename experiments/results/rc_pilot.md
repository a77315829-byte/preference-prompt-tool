# 요청 대조 규칙 비교 (calibration) — 판정에 쓰지 않는다 (pilot)

- 생성: 2026-11-03T16:54:03.003970+00:00 · 모드 `execute` · 모델 `openai/gpt-4o-mini` · 반복 1 · temperature 0.7
- 추가 규칙: 코드를 내기 전에 개발 요청에 따옴표로 적힌 화면 문구, 버튼 글자, 표시 형식을 하나씩 대조하라. 글자를 바꾸거나 덧붙이지 말고, 요청에 없는 라이브러리(예: styled-components)를 쓰지 마라.

| 조건 | 출력 | 축 검사 통과율 | 기능 통과율 | 기능 미확인 |
|---|---|---|---|---|
| none | 16 | 0.5 | None | None |
| rule_based | 16 | 0.8333 | None | None |
| request_check | 16 | 0.6458 | None | None |

| 짝 | 단위 | 축 검사 차이 [95%] | 기능 차이 [95%] |
|---|---|---|---|
| request_check-rule_based | 16 | -0.1875 (-0.3542, -0.0208) | None None |
| rule_based-none | 16 | 0.3333 (0.1667, 0.5) | None None |

- 사전등록 기준: {"functional_gain": null, "style_non_inferior": false} → 전부 충족: `None`
- (보고용) 기본 조립본 기능 저하 재현: `None`
- 사용량(공급자 보고, 청구서 아님): {"generation_requests": 1, "input_tokens": 734, "output_tokens": 743, "unknown_usage_requests": 0, "elapsed_seconds": 12.77}
- 정적 축 검사와 과제별 고정 시나리오는 기능 동일성이나 사용자 만족을 입증하지 않는다. 과제·프로필 단위의 작은 차이는 결론으로 쓰지 않는다 (절대 규칙 11).
