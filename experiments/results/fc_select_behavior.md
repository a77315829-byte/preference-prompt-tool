# 기능 저하 원인 비교 — select (cached-only)

- 생성: 2026-11-04T03:06:45.623717+00:00 · 모델 `openai/gpt-4o-mini` · 반복 [0] · temperature 0.7
- 사용량(공급자 보고, 청구서 아님): {"generation_requests": 0, "input_tokens": 0, "output_tokens": 0, "unknown_usage_requests": 0, "elapsed_seconds": 118.31}

| 과제 | (a)(b) 합친 기능 통과율 | 고름 |
|---|---|---|
| page_list | 1.0 |  |
| tip_calc | 1.0 |  |
| tag_input | 0.6 | 예 |
| step_wizard | 0.0 |  |
| category_filter | 1.0 |  |
| price_sort | 0.0 |  |
| single_accordion | 1.0 |  |
| bounded_counter | 0.8 | 예 |

- 규칙: 범위 [0.4, 0.85], 0.6 에 가까운 순, 최대 5개, 3개 미만이면 확증 안 함 → 고른 과제 ['tag_input', 'bounded_counter'] (충분: `False`)
