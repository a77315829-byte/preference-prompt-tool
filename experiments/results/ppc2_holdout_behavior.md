# 개인화 프롬프트 3조건 비교

- 생성: 2026-11-03T08:04:42.237516+00:00 · 모드: `cached-only` · 모델: `openai/gpt-4o-mini` · 언어: `ko` · split `holdout_v2` · 반복 3 · temperature 0.7
- 목표 선호 `{"code_structure": "separated", "style_management": "theme", "type_detail": "explicit"}` → 개선 단계 `ai_improved` · (c) 출처 `ai_improved`
- 목표 선호 `{"code_structure": "compact", "style_management": "direct", "type_detail": "inferred"}` → 개선 단계 `ai_improved` · (c) 출처 `ai_improved`
- 목표 선호 `{"code_structure": "compact", "style_management": "theme", "type_detail": "inferred"}` → 개선 단계 `ai_improved` · (c) 출처 `ai_improved`
- 목표 선호 `{"code_structure": "separated", "style_management": "direct", "type_detail": "explicit"}` → 개선 단계 `ai_improved` · (c) 출처 `ai_improved`
- 새 API 요청: 생성 0회, 개선 0회 · 토큰(공급자 보고, 청구서 아님) 입력 0 / 출력 0 · 경과 243.18초
- 주의: Style checks are static. The independent behavior check covers only the task's frozen acceptance scenario; neither shows functional equivalence on all inputs or user satisfaction. With few tasks, differences are anecdotes.

| 과제 | 조건 | 파일 구성 | 스타일 관리 | 타입 작성 | 스타일 전부 | 파일 수 | 테마 신호 | 타입 신호 | 품질 문제 | 타입 검사 | 빌드 | 동작 시나리오 | 기능 통과(독립) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| tab_switch · separated-theme-explicit · r0 | none | ❌ 0.5 | ❌ 0.0 | ❌ 0.6 | 아니오 | 1 | 0 | 3 | 3 | ✅ | ✅ | passed (3/3) | ✅ |
| tab_switch · separated-theme-explicit · r0 | rule_based | ✅ 1.0 | ❌ 0.0 | ❌ 0.6 | 아니오 | 2 | 0 | 3 | 2 | 미확인 | 미확인 | not_run | 미확인 |
| tab_switch · separated-theme-explicit · r0 | ai_improved | ✅ 1.0 | ✅ 1.0 | ❌ 0.8 | 아니오 | 2 | 18 | 4 | 1 | ❌ | ❌ | not_run | ❌ |
| tab_switch · separated-theme-explicit · r1 | none | ❌ 0.5 | ❌ 0.0 | ❌ 0.6 | 아니오 | 1 | 0 | 3 | 3 | ✅ | ✅ | passed (3/3) | ✅ |
| tab_switch · separated-theme-explicit · r1 | rule_based | ❌ 0.5 | ❌ 0.0 | ❌ 0.6 | 아니오 | 1 | 0 | 3 | 3 | ✅ | ✅ | passed (3/3) | ✅ |
| tab_switch · separated-theme-explicit · r1 | ai_improved | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 3 | 21 | 5 | 1 | 미확인 | 미확인 | not_run | 미확인 |
| tab_switch · separated-theme-explicit · r2 | none | ❌ 0.5 | ❌ 0.0 | ❌ 0.6 | 아니오 | 1 | 0 | 3 | 3 | ✅ | ✅ | passed (3/3) | ✅ |
| tab_switch · separated-theme-explicit · r2 | rule_based | ✅ 1.0 | ❌ 0.0 | ❌ 0.6 | 아니오 | 2 | 0 | 3 | 2 | ✅ | ✅ | passed (3/3) | ✅ |
| tab_switch · separated-theme-explicit · r2 | ai_improved | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 2 | 0 | 5 | 1 | ✅ | ✅ | passed (3/3) | ✅ |
| char_counter · separated-theme-explicit · r0 | none | ❌ 0.5 | ❌ 0.0 | ❌ 0.8 | 아니오 | 1 | 0 | 4 | 3 | ✅ | ✅ | failed (3/4) | ❌ |
| char_counter · separated-theme-explicit · r0 | rule_based | ✅ 1.0 | ✅ 1.0 | ❌ 0.8 | 아니오 | 2 | 8 | 4 | 1 | ✅ | ✅ | failed (3/4) | ❌ |
| char_counter · separated-theme-explicit · r0 | ai_improved | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 4 | 0 | 7 | 3 | 미확인 | 미확인 | not_run | 미확인 |
| char_counter · separated-theme-explicit · r1 | none | ❌ 0.5 | ❌ 0.0 | ❌ 0.8 | 아니오 | 1 | 0 | 4 | 3 | ✅ | ✅ | failed (3/4) | ❌ |
| char_counter · separated-theme-explicit · r1 | rule_based | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 3 | 0 | 6 | 2 | 미확인 | 미확인 | not_run | 미확인 |
| char_counter · separated-theme-explicit · r1 | ai_improved | ✅ 1.0 | ✅ 1.0 | ❌ 0.8 | 아니오 | 2 | 20 | 4 | 1 | ✅ | ✅ | failed (3/4) | ❌ |
| char_counter · separated-theme-explicit · r2 | none | ❌ 0.5 | ❌ 0.0 | ❌ 0.8 | 아니오 | 1 | 0 | 4 | 3 | ✅ | ✅ | failed (3/4) | ❌ |
| char_counter · separated-theme-explicit · r2 | rule_based | ✅ 1.0 | ❌ 0.0 | ❌ 0.8 | 아니오 | 2 | 0 | 4 | 2 | ❌ | ✅ | not_run | ❌ |
| char_counter · separated-theme-explicit · r2 | ai_improved | ✅ 1.0 | ✅ 1.0 | ❌ 0.8 | 아니오 | 2 | 19 | 4 | 1 | ✅ | ✅ | failed (3/4) | ❌ |
| star_rating · separated-theme-explicit · r0 | none | ❌ 0.5 | ❌ 0.0 | ❌ 0.8 | 아니오 | 1 | 0 | 4 | 3 | ✅ | ✅ | passed (3/3) | ✅ |
| star_rating · separated-theme-explicit · r0 | rule_based | ❌ 0.5 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 5 | 2 | ❌ | ❌ | not_run | ❌ |
| star_rating · separated-theme-explicit · r0 | ai_improved | ✅ 1.0 | ❌ 0.0 | ❌ 0.8 | 아니오 | 2 | 0 | 4 | 2 | ❌ | ❌ | not_run | ❌ |
| star_rating · separated-theme-explicit · r1 | none | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 2 | 0 | 6 | 1 | 미확인 | 미확인 | not_run | 미확인 |
| star_rating · separated-theme-explicit · r1 | rule_based | ✅ 1.0 | ❌ 0.0 | ❌ 0.8 | 아니오 | 2 | 0 | 4 | 2 | ✅ | ✅ | passed (3/3) | ✅ |
| star_rating · separated-theme-explicit · r1 | ai_improved | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 3 | 0 | 6 | 2 | ✅ | ✅ | passed (3/3) | ✅ |
| star_rating · separated-theme-explicit · r2 | none | ❌ 0.5 | ❌ 0.0 | ❌ 0.8 | 아니오 | 1 | 0 | 4 | 3 | ✅ | ✅ | passed (3/3) | ✅ |
| star_rating · separated-theme-explicit · r2 | rule_based | ❌ 0.5 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 5 | 2 | ❌ | ❌ | not_run | ❌ |
| star_rating · separated-theme-explicit · r2 | ai_improved | ✅ 1.0 | ❌ 0.0 | ❌ 0.6 | 아니오 | 2 | 0 | 3 | 2 | ❌ | ❌ | not_run | ❌ |
| like_toggle · separated-theme-explicit · r0 | none | ❌ 0.5 | ❌ 0.0 | ❌ 0.8 | 아니오 | 1 | 0 | 4 | 3 | ✅ | ✅ | passed (3/3) | ✅ |
| like_toggle · separated-theme-explicit · r0 | rule_based | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 3 | 0 | 7 | 3 | 미확인 | 미확인 | not_run | 미확인 |
| like_toggle · separated-theme-explicit · r0 | ai_improved | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 3 | 0 | 6 | 3 | 미확인 | 미확인 | not_run | 미확인 |
| like_toggle · separated-theme-explicit · r1 | none | ❌ 0.5 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 6 | 3 | ✅ | ✅ | error | ❌ |
| like_toggle · separated-theme-explicit · r1 | rule_based | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 4 | 0 | 6 | 3 | 미확인 | 미확인 | not_run | 미확인 |
| like_toggle · separated-theme-explicit · r1 | ai_improved | ✅ 1.0 | ❌ 0.0 | ❌ 0.8 | 아니오 | 2 | 0 | 4 | 2 | ✅ | ✅ | error | ❌ |
| like_toggle · separated-theme-explicit · r2 | none | ❌ 0.5 | ❌ 0.0 | ❌ 0.8 | 아니오 | 1 | 0 | 4 | 3 | ✅ | ✅ | error | ❌ |
| like_toggle · separated-theme-explicit · r2 | rule_based | ✅ 1.0 | ✅ 1.0 | ❌ 0.8 | 아니오 | 2 | 9 | 4 | 1 | ✅ | ✅ | error | ❌ |
| like_toggle · separated-theme-explicit · r2 | ai_improved | ✅ 1.0 | ❌ 0.0 | ❌ 0.8 | 아니오 | 2 | 0 | 4 | 2 | ✅ | ✅ | error | ❌ |
| temperature_convert · separated-theme-explicit · r0 | none | ❌ 0.5 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 7 | 2 | ✅ | ✅ | passed (4/4) | ✅ |
| temperature_convert · separated-theme-explicit · r0 | rule_based | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 3 | 7 | 6 | 1 | ✅ | ✅ | failed (3/4) | ❌ |
| temperature_convert · separated-theme-explicit · r0 | ai_improved | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 4 | 0 | 7 | 3 | 미확인 | 미확인 | not_run | 미확인 |
| temperature_convert · separated-theme-explicit · r1 | none | ❌ 0.5 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 5 | 2 | ✅ | ✅ | failed (3/4) | ❌ |
| temperature_convert · separated-theme-explicit · r1 | rule_based | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 3 | 13 | 8 | 0 | ✅ | ✅ | passed (4/4) | ✅ |
| temperature_convert · separated-theme-explicit · r1 | ai_improved | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 3 | 6 | 5 | 0 | ✅ | ✅ | failed (1/4) | ❌ |
| temperature_convert · separated-theme-explicit · r2 | none | ❌ 0.5 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 5 | 2 | ✅ | ✅ | passed (4/4) | ✅ |
| temperature_convert · separated-theme-explicit · r2 | rule_based | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 2 | 0 | 5 | 1 | ❌ | ❌ | not_run | ❌ |
| temperature_convert · separated-theme-explicit · r2 | ai_improved | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 2 | 13 | 5 | 0 | ✅ | ✅ | failed (3/4) | ❌ |
| tab_switch · compact-direct-inferred · r0 | none | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 3 | 1 | ✅ | ✅ | passed (3/3) | ✅ |
| tab_switch · compact-direct-inferred · r0 | rule_based | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 3 | 1 | ✅ | ✅ | passed (3/3) | ✅ |
| tab_switch · compact-direct-inferred · r0 | ai_improved | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 3 | 1 | ✅ | ✅ | passed (3/3) | ✅ |
| tab_switch · compact-direct-inferred · r1 | none | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 3 | 1 | ✅ | ✅ | passed (3/3) | ✅ |
| tab_switch · compact-direct-inferred · r1 | rule_based | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 1 | 0 | ✅ | ✅ | passed (3/3) | ✅ |
| tab_switch · compact-direct-inferred · r1 | ai_improved | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 3 | 1 | ✅ | ✅ | passed (3/3) | ✅ |
| tab_switch · compact-direct-inferred · r2 | none | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 3 | 1 | ✅ | ✅ | passed (3/3) | ✅ |
| tab_switch · compact-direct-inferred · r2 | rule_based | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 3 | 1 | ✅ | ✅ | passed (3/3) | ✅ |
| tab_switch · compact-direct-inferred · r2 | ai_improved | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 3 | 1 | ✅ | ✅ | passed (3/3) | ✅ |
| char_counter · compact-direct-inferred · r0 | none | ✅ 1.0 | ✅ 1.0 | ❌ 0.75 | 아니오 | 1 | 0 | 4 | 1 | ✅ | ✅ | failed (3/4) | ❌ |
| char_counter · compact-direct-inferred · r0 | rule_based | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 3 | 1 | ✅ | ✅ | failed (3/4) | ❌ |
| char_counter · compact-direct-inferred · r0 | ai_improved | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 3 | 1 | ✅ | ✅ | failed (3/4) | ❌ |
| char_counter · compact-direct-inferred · r1 | none | ✅ 1.0 | ✅ 1.0 | ❌ 0.75 | 아니오 | 1 | 0 | 4 | 1 | ✅ | ✅ | failed (3/4) | ❌ |
| char_counter · compact-direct-inferred · r1 | rule_based | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 3 | 1 | ✅ | ✅ | failed (3/4) | ❌ |
| char_counter · compact-direct-inferred · r1 | ai_improved | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 3 | 1 | ✅ | ✅ | failed (3/4) | ❌ |
| char_counter · compact-direct-inferred · r2 | none | ✅ 1.0 | ✅ 1.0 | ❌ 0.75 | 아니오 | 1 | 0 | 4 | 1 | ✅ | ✅ | failed (3/4) | ❌ |
| char_counter · compact-direct-inferred · r2 | rule_based | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 3 | 1 | ✅ | ✅ | failed (3/4) | ❌ |
| char_counter · compact-direct-inferred · r2 | ai_improved | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 3 | 1 | ✅ | ✅ | failed (3/4) | ❌ |
| star_rating · compact-direct-inferred · r0 | none | ✅ 1.0 | ✅ 1.0 | ❌ 0.75 | 아니오 | 1 | 0 | 4 | 1 | ✅ | ✅ | passed (3/3) | ✅ |
| star_rating · compact-direct-inferred · r0 | rule_based | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 3 | 1 | ✅ | ✅ | passed (3/3) | ✅ |
| star_rating · compact-direct-inferred · r0 | ai_improved | ✅ 1.0 | ✅ 1.0 | ❌ 0.75 | 아니오 | 1 | 0 | 4 | 1 | ✅ | ✅ | passed (3/3) | ✅ |
| star_rating · compact-direct-inferred · r1 | none | ❌ 0.5 | ✅ 1.0 | ❌ 0.5 | 아니오 | 2 | 0 | 6 | 2 | 미확인 | 미확인 | not_run | 미확인 |
| star_rating · compact-direct-inferred · r1 | rule_based | ✅ 1.0 | ✅ 1.0 | ❌ 0.75 | 아니오 | 1 | 0 | 4 | 1 | ✅ | ✅ | passed (3/3) | ✅ |
| star_rating · compact-direct-inferred · r1 | ai_improved | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 3 | 1 | ✅ | ✅ | passed (3/3) | ✅ |
| star_rating · compact-direct-inferred · r2 | none | ✅ 1.0 | ✅ 1.0 | ❌ 0.75 | 아니오 | 1 | 0 | 4 | 1 | ✅ | ✅ | passed (3/3) | ✅ |
| star_rating · compact-direct-inferred · r2 | rule_based | ✅ 1.0 | ✅ 1.0 | ❌ 0.75 | 아니오 | 1 | 0 | 4 | 1 | ✅ | ✅ | passed (3/3) | ✅ |
| star_rating · compact-direct-inferred · r2 | ai_improved | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 3 | 1 | ✅ | ✅ | passed (3/3) | ✅ |
| like_toggle · compact-direct-inferred · r0 | none | ✅ 1.0 | ✅ 1.0 | ❌ 0.75 | 아니오 | 1 | 0 | 4 | 1 | ✅ | ✅ | passed (3/3) | ✅ |
| like_toggle · compact-direct-inferred · r0 | rule_based | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 2 | 1 | ✅ | ✅ | error | ❌ |
| like_toggle · compact-direct-inferred · r0 | ai_improved | ✅ 1.0 | ✅ 1.0 | ❌ 0.75 | 아니오 | 1 | 0 | 4 | 1 | ✅ | ✅ | error | ❌ |
| like_toggle · compact-direct-inferred · r1 | none | ✅ 1.0 | ✅ 1.0 | ❌ 0.5 | 아니오 | 1 | 0 | 6 | 2 | ✅ | ✅ | error | ❌ |
| like_toggle · compact-direct-inferred · r1 | rule_based | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 0 | 0 | ✅ | ✅ | error | ❌ |
| like_toggle · compact-direct-inferred · r1 | ai_improved | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 2 | 1 | ✅ | ✅ | error | ❌ |
| like_toggle · compact-direct-inferred · r2 | none | ✅ 1.0 | ✅ 1.0 | ❌ 0.75 | 아니오 | 1 | 0 | 4 | 1 | ✅ | ✅ | error | ❌ |
| like_toggle · compact-direct-inferred · r2 | rule_based | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 2 | 1 | ✅ | ✅ | error | ❌ |
| like_toggle · compact-direct-inferred · r2 | ai_improved | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 2 | 1 | ✅ | ✅ | error | ❌ |
| temperature_convert · compact-direct-inferred · r0 | none | ✅ 1.0 | ✅ 1.0 | ❌ 0.429 | 아니오 | 1 | 0 | 7 | 1 | ✅ | ✅ | passed (4/4) | ✅ |
| temperature_convert · compact-direct-inferred · r0 | rule_based | ✅ 1.0 | ✅ 1.0 | ❌ 0.75 | 아니오 | 1 | 0 | 4 | 1 | ✅ | ✅ | failed (1/4) | ❌ |
| temperature_convert · compact-direct-inferred · r0 | ai_improved | ✅ 1.0 | ✅ 1.0 | ❌ 0.75 | 아니오 | 1 | 0 | 4 | 1 | ✅ | ✅ | failed (3/4) | ❌ |
| temperature_convert · compact-direct-inferred · r1 | none | ✅ 1.0 | ✅ 1.0 | ❌ 0.6 | 아니오 | 1 | 0 | 5 | 1 | ✅ | ✅ | failed (3/4) | ❌ |
| temperature_convert · compact-direct-inferred · r1 | rule_based | ✅ 1.0 | ✅ 1.0 | ❌ 0.75 | 아니오 | 1 | 0 | 4 | 1 | ✅ | ✅ | failed (2/4) | ❌ |
| temperature_convert · compact-direct-inferred · r1 | ai_improved | ✅ 1.0 | ✅ 1.0 | ❌ 0.6 | 아니오 | 1 | 0 | 5 | 1 | ✅ | ✅ | failed (1/4) | ❌ |
| temperature_convert · compact-direct-inferred · r2 | none | ✅ 1.0 | ✅ 1.0 | ❌ 0.6 | 아니오 | 1 | 0 | 5 | 1 | ✅ | ✅ | passed (4/4) | ✅ |
| temperature_convert · compact-direct-inferred · r2 | rule_based | ✅ 1.0 | ✅ 1.0 | ❌ 0.75 | 아니오 | 1 | 0 | 4 | 1 | ✅ | ✅ | failed (3/4) | ❌ |
| temperature_convert · compact-direct-inferred · r2 | ai_improved | ✅ 1.0 | ✅ 1.0 | ❌ 0.75 | 아니오 | 1 | 0 | 4 | 1 | ✅ | ✅ | failed (3/4) | ❌ |
| tab_switch · compact-theme-inferred · r0 | none | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 3 | 2 | ✅ | ✅ | passed (3/3) | ✅ |
| tab_switch · compact-theme-inferred · r0 | rule_based | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 1 | 1 | ✅ | ✅ | passed (3/3) | ✅ |
| tab_switch · compact-theme-inferred · r0 | ai_improved | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 1 | 1 | ✅ | ✅ | passed (3/3) | ✅ |
| tab_switch · compact-theme-inferred · r1 | none | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 3 | 2 | ✅ | ✅ | passed (3/3) | ✅ |
| tab_switch · compact-theme-inferred · r1 | rule_based | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 3 | 2 | ✅ | ✅ | passed (3/3) | ✅ |
| tab_switch · compact-theme-inferred · r1 | ai_improved | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 1 | 1 | ✅ | ✅ | passed (3/3) | ✅ |
| tab_switch · compact-theme-inferred · r2 | none | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 3 | 2 | ✅ | ✅ | passed (3/3) | ✅ |
| tab_switch · compact-theme-inferred · r2 | rule_based | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 13 | 3 | 1 | ✅ | ✅ | passed (3/3) | ✅ |
| tab_switch · compact-theme-inferred · r2 | ai_improved | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 1 | 1 | ✅ | ✅ | passed (3/3) | ✅ |
| char_counter · compact-theme-inferred · r0 | none | ✅ 1.0 | ❌ 0.0 | ❌ 0.75 | 아니오 | 1 | 0 | 4 | 2 | ✅ | ✅ | failed (3/4) | ❌ |
| char_counter · compact-theme-inferred · r0 | rule_based | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 1 | 1 | ✅ | ✅ | failed (3/4) | ❌ |
| char_counter · compact-theme-inferred · r0 | ai_improved | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 3 | 2 | ✅ | ✅ | failed (3/4) | ❌ |
| char_counter · compact-theme-inferred · r1 | none | ✅ 1.0 | ❌ 0.0 | ❌ 0.75 | 아니오 | 1 | 0 | 4 | 2 | ✅ | ✅ | failed (3/4) | ❌ |
| char_counter · compact-theme-inferred · r1 | rule_based | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 1 | 1 | ✅ | ✅ | failed (3/4) | ❌ |
| char_counter · compact-theme-inferred · r1 | ai_improved | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 1 | 1 | ✅ | ✅ | failed (3/4) | ❌ |
| char_counter · compact-theme-inferred · r2 | none | ✅ 1.0 | ❌ 0.0 | ❌ 0.75 | 아니오 | 1 | 0 | 4 | 2 | ✅ | ✅ | failed (3/4) | ❌ |
| char_counter · compact-theme-inferred · r2 | rule_based | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 1 | 1 | ✅ | ✅ | failed (3/4) | ❌ |
| char_counter · compact-theme-inferred · r2 | ai_improved | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 3 | 2 | ✅ | ✅ | failed (3/4) | ❌ |
| star_rating · compact-theme-inferred · r0 | none | ✅ 1.0 | ❌ 0.0 | ❌ 0.75 | 아니오 | 1 | 0 | 4 | 2 | ✅ | ✅ | passed (3/3) | ✅ |
| star_rating · compact-theme-inferred · r0 | rule_based | ✅ 1.0 | ❌ 0.0 | ❌ 0.75 | 아니오 | 1 | 0 | 4 | 2 | ✅ | ✅ | passed (3/3) | ✅ |
| star_rating · compact-theme-inferred · r0 | ai_improved | ✅ 1.0 | ❌ 0.0 | ❌ 0.75 | 아니오 | 1 | 0 | 4 | 2 | ✅ | ✅ | passed (3/3) | ✅ |
| star_rating · compact-theme-inferred · r1 | none | ❌ 0.5 | ❌ 0.0 | ❌ 0.5 | 아니오 | 2 | 0 | 6 | 3 | 미확인 | 미확인 | not_run | 미확인 |
| star_rating · compact-theme-inferred · r1 | rule_based | ✅ 1.0 | ❌ 0.0 | ❌ 0.75 | 아니오 | 1 | 0 | 4 | 2 | ✅ | ✅ | passed (3/3) | ✅ |
| star_rating · compact-theme-inferred · r1 | ai_improved | ✅ 1.0 | ❌ 0.0 | ❌ 0.75 | 아니오 | 1 | 0 | 4 | 2 | ❌ | ✅ | not_run | ❌ |
| star_rating · compact-theme-inferred · r2 | none | ✅ 1.0 | ❌ 0.0 | ❌ 0.75 | 아니오 | 1 | 0 | 4 | 2 | ✅ | ✅ | passed (3/3) | ✅ |
| star_rating · compact-theme-inferred · r2 | rule_based | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 3 | 2 | ✅ | ✅ | passed (3/3) | ✅ |
| star_rating · compact-theme-inferred · r2 | ai_improved | ✅ 1.0 | ❌ 0.0 | ❌ 0.75 | 아니오 | 1 | 0 | 4 | 2 | ❌ | ✅ | not_run | ❌ |
| like_toggle · compact-theme-inferred · r0 | none | ✅ 1.0 | ❌ 0.0 | ❌ 0.75 | 아니오 | 1 | 0 | 4 | 2 | ✅ | ✅ | passed (3/3) | ✅ |
| like_toggle · compact-theme-inferred · r0 | rule_based | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 2 | 2 | ✅ | ✅ | error | ❌ |
| like_toggle · compact-theme-inferred · r0 | ai_improved | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 0 | 1 | ✅ | ✅ | error | ❌ |
| like_toggle · compact-theme-inferred · r1 | none | ✅ 1.0 | ❌ 0.0 | ❌ 0.5 | 아니오 | 1 | 0 | 6 | 3 | ✅ | ✅ | error | ❌ |
| like_toggle · compact-theme-inferred · r1 | rule_based | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 2 | 2 | ✅ | ✅ | error | ❌ |
| like_toggle · compact-theme-inferred · r1 | ai_improved | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 2 | 2 | ✅ | ✅ | error | ❌ |
| like_toggle · compact-theme-inferred · r2 | none | ✅ 1.0 | ❌ 0.0 | ❌ 0.75 | 아니오 | 1 | 0 | 4 | 2 | ✅ | ✅ | error | ❌ |
| like_toggle · compact-theme-inferred · r2 | rule_based | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 2 | 2 | ✅ | ✅ | error | ❌ |
| like_toggle · compact-theme-inferred · r2 | ai_improved | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 0 | 1 | ✅ | ✅ | error | ❌ |
| temperature_convert · compact-theme-inferred · r0 | none | ✅ 1.0 | ❌ 0.0 | ❌ 0.429 | 아니오 | 1 | 0 | 7 | 2 | ✅ | ✅ | passed (4/4) | ✅ |
| temperature_convert · compact-theme-inferred · r0 | rule_based | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 2 | 1 | ✅ | ✅ | failed (3/4) | ❌ |
| temperature_convert · compact-theme-inferred · r0 | ai_improved | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 2 | 1 | ✅ | ✅ | failed (3/4) | ❌ |
| temperature_convert · compact-theme-inferred · r1 | none | ✅ 1.0 | ❌ 0.0 | ❌ 0.6 | 아니오 | 1 | 0 | 5 | 2 | ✅ | ✅ | failed (3/4) | ❌ |
| temperature_convert · compact-theme-inferred · r1 | rule_based | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 2 | 1 | ✅ | ✅ | failed (2/4) | ❌ |
| temperature_convert · compact-theme-inferred · r1 | ai_improved | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 2 | 1 | ✅ | ✅ | failed (3/4) | ❌ |
| temperature_convert · compact-theme-inferred · r2 | none | ✅ 1.0 | ❌ 0.0 | ❌ 0.6 | 아니오 | 1 | 0 | 5 | 2 | ✅ | ✅ | passed (4/4) | ✅ |
| temperature_convert · compact-theme-inferred · r2 | rule_based | ✅ 1.0 | ❌ 0.0 | ❌ 0.6 | 아니오 | 1 | 0 | 5 | 2 | ✅ | ✅ | failed (1/4) | ❌ |
| temperature_convert · compact-theme-inferred · r2 | ai_improved | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 2 | 1 | ✅ | ✅ | failed (2/4) | ❌ |
| tab_switch · separated-direct-explicit · r0 | none | ❌ 0.5 | ✅ 1.0 | ❌ 0.6 | 아니오 | 1 | 0 | 3 | 2 | ✅ | ✅ | passed (3/3) | ✅ |
| tab_switch · separated-direct-explicit · r0 | rule_based | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 2 | 0 | 5 | 1 | 미확인 | 미확인 | not_run | 미확인 |
| tab_switch · separated-direct-explicit · r0 | ai_improved | ❌ 0.5 | ✅ 1.0 | ✅ 1.0 | 아니오 | 1 | 0 | 5 | 1 | ✅ | ✅ | passed (3/3) | ✅ |
| tab_switch · separated-direct-explicit · r1 | none | ❌ 0.5 | ✅ 1.0 | ❌ 0.6 | 아니오 | 1 | 0 | 3 | 2 | ✅ | ✅ | passed (3/3) | ✅ |
| tab_switch · separated-direct-explicit · r1 | rule_based | ✅ 1.0 | ✅ 1.0 | ❌ 0.6 | 아니오 | 2 | 0 | 3 | 1 | ✅ | ✅ | passed (3/3) | ✅ |
| tab_switch · separated-direct-explicit · r1 | ai_improved | ❌ 0.5 | ✅ 1.0 | ✅ 1.0 | 아니오 | 1 | 0 | 5 | 1 | ✅ | ✅ | passed (3/3) | ✅ |
| tab_switch · separated-direct-explicit · r2 | none | ❌ 0.5 | ✅ 1.0 | ❌ 0.6 | 아니오 | 1 | 0 | 3 | 2 | ✅ | ✅ | passed (3/3) | ✅ |
| tab_switch · separated-direct-explicit · r2 | rule_based | ❌ 0.5 | ✅ 1.0 | ❌ 0.6 | 아니오 | 1 | 0 | 3 | 2 | ✅ | ✅ | passed (3/3) | ✅ |
| tab_switch · separated-direct-explicit · r2 | ai_improved | ❌ 0.5 | ✅ 1.0 | ❌ 0.6 | 아니오 | 1 | 0 | 3 | 2 | ✅ | ✅ | passed (3/3) | ✅ |
| char_counter · separated-direct-explicit · r0 | none | ❌ 0.5 | ✅ 1.0 | ❌ 0.8 | 아니오 | 1 | 0 | 4 | 2 | ✅ | ✅ | failed (3/4) | ❌ |
| char_counter · separated-direct-explicit · r0 | rule_based | ✅ 1.0 | ✅ 1.0 | ❌ 0.8 | 아니오 | 2 | 0 | 4 | 1 | ✅ | ✅ | failed (3/4) | ❌ |
| char_counter · separated-direct-explicit · r0 | ai_improved | ✅ 1.0 | ✅ 1.0 | ❌ 0.8 | 아니오 | 2 | 0 | 4 | 2 | ✅ | ✅ | failed (3/4) | ❌ |
| char_counter · separated-direct-explicit · r1 | none | ❌ 0.5 | ✅ 1.0 | ❌ 0.8 | 아니오 | 1 | 0 | 4 | 2 | ✅ | ✅ | failed (3/4) | ❌ |
| char_counter · separated-direct-explicit · r1 | rule_based | ✅ 1.0 | ✅ 1.0 | ❌ 0.8 | 아니오 | 2 | 0 | 4 | 1 | ✅ | ✅ | failed (3/4) | ❌ |
| char_counter · separated-direct-explicit · r1 | ai_improved | ✅ 1.0 | ✅ 1.0 | ❌ 0.8 | 아니오 | 2 | 0 | 4 | 1 | ✅ | ✅ | failed (3/4) | ❌ |
| char_counter · separated-direct-explicit · r2 | none | ❌ 0.5 | ✅ 1.0 | ❌ 0.8 | 아니오 | 1 | 0 | 4 | 2 | ✅ | ✅ | failed (3/4) | ❌ |
| char_counter · separated-direct-explicit · r2 | rule_based | ✅ 1.0 | ✅ 1.0 | ❌ 0.8 | 아니오 | 2 | 0 | 4 | 1 | ✅ | ✅ | failed (3/4) | ❌ |
| char_counter · separated-direct-explicit · r2 | ai_improved | ❌ 0.5 | ✅ 1.0 | ❌ 0.8 | 아니오 | 1 | 0 | 4 | 2 | ✅ | ✅ | failed (3/4) | ❌ |
| star_rating · separated-direct-explicit · r0 | none | ❌ 0.5 | ✅ 1.0 | ❌ 0.8 | 아니오 | 1 | 0 | 4 | 2 | ✅ | ✅ | passed (3/3) | ✅ |
| star_rating · separated-direct-explicit · r0 | rule_based | ✅ 1.0 | ✅ 1.0 | ❌ 0.8 | 아니오 | 2 | 0 | 4 | 1 | ✅ | ✅ | passed (3/3) | ✅ |
| star_rating · separated-direct-explicit · r0 | ai_improved | ✅ 1.0 | ✅ 1.0 | ❌ 0.8 | 아니오 | 2 | 0 | 4 | 1 | ✅ | ✅ | passed (3/3) | ✅ |
| star_rating · separated-direct-explicit · r1 | none | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 2 | 0 | 6 | 0 | 미확인 | 미확인 | not_run | 미확인 |
| star_rating · separated-direct-explicit · r1 | rule_based | ✅ 1.0 | ✅ 1.0 | ❌ 0.8 | 아니오 | 2 | 0 | 4 | 1 | ✅ | ✅ | passed (3/3) | ✅ |
| star_rating · separated-direct-explicit · r1 | ai_improved | ✅ 1.0 | ✅ 1.0 | ❌ 0.8 | 아니오 | 2 | 0 | 4 | 1 | ✅ | ✅ | passed (3/3) | ✅ |
| star_rating · separated-direct-explicit · r2 | none | ❌ 0.5 | ✅ 1.0 | ❌ 0.8 | 아니오 | 1 | 0 | 4 | 2 | ✅ | ✅ | passed (3/3) | ✅ |
| star_rating · separated-direct-explicit · r2 | rule_based | ✅ 1.0 | ✅ 1.0 | ❌ 0.8 | 아니오 | 2 | 0 | 4 | 1 | ✅ | ✅ | passed (3/3) | ✅ |
| star_rating · separated-direct-explicit · r2 | ai_improved | ✅ 1.0 | ✅ 1.0 | ❌ 0.8 | 아니오 | 2 | 0 | 4 | 1 | ✅ | ✅ | passed (3/3) | ✅ |
| like_toggle · separated-direct-explicit · r0 | none | ❌ 0.5 | ✅ 1.0 | ❌ 0.8 | 아니오 | 1 | 0 | 4 | 2 | ✅ | ✅ | passed (3/3) | ✅ |
| like_toggle · separated-direct-explicit · r0 | rule_based | ✅ 1.0 | ✅ 1.0 | ❌ 0.8 | 아니오 | 2 | 0 | 4 | 1 | ✅ | ✅ | error | ❌ |
| like_toggle · separated-direct-explicit · r0 | ai_improved | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 3 | 0 | 6 | 2 | 미확인 | 미확인 | not_run | 미확인 |
| like_toggle · separated-direct-explicit · r1 | none | ❌ 0.5 | ✅ 1.0 | ✅ 1.0 | 아니오 | 1 | 0 | 6 | 2 | ✅ | ✅ | error | ❌ |
| like_toggle · separated-direct-explicit · r1 | rule_based | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 2 | 0 | 6 | 1 | 미확인 | 미확인 | not_run | 미확인 |
| like_toggle · separated-direct-explicit · r1 | ai_improved | ✅ 1.0 | ✅ 1.0 | ❌ 0.8 | 아니오 | 2 | 0 | 4 | 1 | ✅ | ✅ | error | ❌ |
| like_toggle · separated-direct-explicit · r2 | none | ❌ 0.5 | ✅ 1.0 | ❌ 0.8 | 아니오 | 1 | 0 | 4 | 2 | ✅ | ✅ | error | ❌ |
| like_toggle · separated-direct-explicit · r2 | rule_based | ✅ 1.0 | ✅ 1.0 | ❌ 0.8 | 아니오 | 2 | 0 | 4 | 1 | ✅ | ✅ | error | ❌ |
| like_toggle · separated-direct-explicit · r2 | ai_improved | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 4 | 0 | 6 | 2 | 미확인 | 미확인 | not_run | 미확인 |
| temperature_convert · separated-direct-explicit · r0 | none | ❌ 0.5 | ✅ 1.0 | ✅ 1.0 | 아니오 | 1 | 0 | 7 | 1 | ✅ | ✅ | passed (4/4) | ✅ |
| temperature_convert · separated-direct-explicit · r0 | rule_based | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 2 | 0 | 5 | 0 | ✅ | ✅ | failed (1/4) | ❌ |
| temperature_convert · separated-direct-explicit · r0 | ai_improved | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 2 | 0 | 7 | 1 | 미확인 | 미확인 | not_run | 미확인 |
| temperature_convert · separated-direct-explicit · r1 | none | ❌ 0.5 | ✅ 1.0 | ✅ 1.0 | 아니오 | 1 | 0 | 5 | 1 | ✅ | ✅ | failed (3/4) | ❌ |
| temperature_convert · separated-direct-explicit · r1 | rule_based | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 2 | 0 | 5 | 0 | ✅ | ✅ | failed (1/4) | ❌ |
| temperature_convert · separated-direct-explicit · r1 | ai_improved | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 4 | 0 | 9 | 2 | 미확인 | 미확인 | not_run | 미확인 |
| temperature_convert · separated-direct-explicit · r2 | none | ❌ 0.5 | ✅ 1.0 | ✅ 1.0 | 아니오 | 1 | 0 | 5 | 1 | ✅ | ✅ | passed (4/4) | ✅ |
| temperature_convert · separated-direct-explicit · r2 | rule_based | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 2 | 0 | 7 | 0 | ✅ | ✅ | failed (1/4) | ❌ |
| temperature_convert · separated-direct-explicit · r2 | ai_improved | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 2 | 0 | 9 | 1 | 미확인 | 미확인 | not_run | 미확인 |

## 집계

| 조건 | 출력 | 누락 | 축 통과율 | 세 축 전부 | 기능 통과율 | 기능 미확인 |
|---|---|---|---|---|---|---|
| none | 60 | 0 | 0.4222 | 0.0667 | 0.5333 | 4 |
| rule_based | 60 | 0 | 0.7 | 0.3 | 0.35 | 6 |
| ai_improved | 60 | 0 | 0.7167 | 0.3 | 0.3 | 9 |

| 짝 비교 | 단위 수 | 축 통과율 차이 [95% 구간] | 기능 통과율 차이 [95% 구간] |
|---|---|---|---|
| ai_improved-rule_based | 60 | 0.0167 (-0.0444, 0.0722) | -0.05 (-0.1333, 0.0167) |
| rule_based-none | 60 | 0.2778 (0.2222, 0.3333) | -0.1833 (-0.3333, -0.05) |

- 사전등록 기준 (확증(판정에 쓴다)): {"style_gain": false, "functional_non_inferior": true, "fallback_rate": true} → 전부 충족: `False` · 미적용 비율 0.0

## 조건 간 차이

- tab_switch#separated-theme-explicit#r0 none vs rule_based: 검사 통과 변화 code_structure: False→True; 신호 files: 1→2; 실행 검사 True→None
- tab_switch#separated-theme-explicit#r0 rule_based vs ai_improved: 검사 통과 변화 style_management: False→True; 신호 theme_signals: 0→18, type_signals: 3→4; 실행 검사 None→False
- tab_switch#separated-theme-explicit#r0 none vs ai_improved: 검사 통과 변화 code_structure: False→True, style_management: False→True; 신호 files: 1→2, theme_signals: 0→18, type_signals: 3→4; 실행 검사 True→False
- tab_switch#separated-theme-explicit#r1 none vs rule_based: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (True)
- tab_switch#separated-theme-explicit#r1 rule_based vs ai_improved: 검사 통과 변화 code_structure: False→True, style_management: False→True, type_detail: False→True; 신호 files: 1→3, theme_signals: 0→21, type_signals: 3→5; 실행 검사 True→None
- tab_switch#separated-theme-explicit#r1 none vs ai_improved: 검사 통과 변화 code_structure: False→True, style_management: False→True, type_detail: False→True; 신호 files: 1→3, theme_signals: 0→21, type_signals: 3→5; 실행 검사 True→None
- tab_switch#separated-theme-explicit#r2 none vs rule_based: 검사 통과 변화 code_structure: False→True; 신호 files: 1→2; 실행 검사 차이 없음 (True)
- tab_switch#separated-theme-explicit#r2 rule_based vs ai_improved: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 3→5; 실행 검사 차이 없음 (True)
- tab_switch#separated-theme-explicit#r2 none vs ai_improved: 검사 통과 변화 code_structure: False→True, type_detail: False→True; 신호 files: 1→2, type_signals: 3→5; 실행 검사 차이 없음 (True)
- char_counter#separated-theme-explicit#r0 none vs rule_based: 검사 통과 변화 code_structure: False→True, style_management: False→True; 신호 files: 1→2, theme_signals: 0→8; 실행 검사 차이 없음 (False)
- char_counter#separated-theme-explicit#r0 rule_based vs ai_improved: 검사 통과 변화 style_management: True→False, type_detail: False→True; 신호 files: 2→4, theme_signals: 8→0, type_signals: 4→7; 실행 검사 False→None
- char_counter#separated-theme-explicit#r0 none vs ai_improved: 검사 통과 변화 code_structure: False→True, type_detail: False→True; 신호 files: 1→4, type_signals: 4→7; 실행 검사 False→None
- char_counter#separated-theme-explicit#r1 none vs rule_based: 검사 통과 변화 code_structure: False→True, type_detail: False→True; 신호 files: 1→3, type_signals: 4→6; 실행 검사 False→None
- char_counter#separated-theme-explicit#r1 rule_based vs ai_improved: 검사 통과 변화 style_management: False→True, type_detail: True→False; 신호 files: 3→2, theme_signals: 0→20, type_signals: 6→4; 실행 검사 None→False
- char_counter#separated-theme-explicit#r1 none vs ai_improved: 검사 통과 변화 code_structure: False→True, style_management: False→True; 신호 files: 1→2, theme_signals: 0→20; 실행 검사 차이 없음 (False)
- char_counter#separated-theme-explicit#r2 none vs rule_based: 검사 통과 변화 code_structure: False→True; 신호 files: 1→2; 실행 검사 차이 없음 (False)
- char_counter#separated-theme-explicit#r2 rule_based vs ai_improved: 검사 통과 변화 style_management: False→True; 신호 theme_signals: 0→19; 실행 검사 차이 없음 (False)
- char_counter#separated-theme-explicit#r2 none vs ai_improved: 검사 통과 변화 code_structure: False→True, style_management: False→True; 신호 files: 1→2, theme_signals: 0→19; 실행 검사 차이 없음 (False)
- star_rating#separated-theme-explicit#r0 none vs rule_based: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 4→5; 실행 검사 True→False
- star_rating#separated-theme-explicit#r0 rule_based vs ai_improved: 검사 통과 변화 code_structure: False→True, type_detail: True→False; 신호 files: 1→2, type_signals: 5→4; 실행 검사 차이 없음 (False)
- star_rating#separated-theme-explicit#r0 none vs ai_improved: 검사 통과 변화 code_structure: False→True; 신호 files: 1→2; 실행 검사 True→False
- star_rating#separated-theme-explicit#r1 none vs rule_based: 검사 통과 변화 type_detail: True→False; 신호 type_signals: 6→4; 실행 검사 None→True
- star_rating#separated-theme-explicit#r1 rule_based vs ai_improved: 검사 통과 변화 type_detail: False→True; 신호 files: 2→3, type_signals: 4→6; 실행 검사 차이 없음 (True)
- star_rating#separated-theme-explicit#r1 none vs ai_improved: 검사 통과 차이 없음; 신호 files: 2→3; 실행 검사 None→True
- star_rating#separated-theme-explicit#r2 none vs rule_based: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 4→5; 실행 검사 True→False
- star_rating#separated-theme-explicit#r2 rule_based vs ai_improved: 검사 통과 변화 code_structure: False→True, type_detail: True→False; 신호 files: 1→2, type_signals: 5→3; 실행 검사 차이 없음 (False)
- star_rating#separated-theme-explicit#r2 none vs ai_improved: 검사 통과 변화 code_structure: False→True; 신호 files: 1→2, type_signals: 4→3; 실행 검사 True→False
- like_toggle#separated-theme-explicit#r0 none vs rule_based: 검사 통과 변화 code_structure: False→True, type_detail: False→True; 신호 files: 1→3, type_signals: 4→7; 실행 검사 True→None
- like_toggle#separated-theme-explicit#r0 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 type_signals: 7→6; 실행 검사 차이 없음 (None)
- like_toggle#separated-theme-explicit#r0 none vs ai_improved: 검사 통과 변화 code_structure: False→True, type_detail: False→True; 신호 files: 1→3, type_signals: 4→6; 실행 검사 True→None
- like_toggle#separated-theme-explicit#r1 none vs rule_based: 검사 통과 변화 code_structure: False→True; 신호 files: 1→4; 실행 검사 False→None
- like_toggle#separated-theme-explicit#r1 rule_based vs ai_improved: 검사 통과 변화 type_detail: True→False; 신호 files: 4→2, type_signals: 6→4; 실행 검사 None→False
- like_toggle#separated-theme-explicit#r1 none vs ai_improved: 검사 통과 변화 code_structure: False→True, type_detail: True→False; 신호 files: 1→2, type_signals: 6→4; 실행 검사 차이 없음 (False)
- like_toggle#separated-theme-explicit#r2 none vs rule_based: 검사 통과 변화 code_structure: False→True, style_management: False→True; 신호 files: 1→2, theme_signals: 0→9; 실행 검사 차이 없음 (False)
- like_toggle#separated-theme-explicit#r2 rule_based vs ai_improved: 검사 통과 변화 style_management: True→False; 신호 theme_signals: 9→0; 실행 검사 차이 없음 (False)
- like_toggle#separated-theme-explicit#r2 none vs ai_improved: 검사 통과 변화 code_structure: False→True; 신호 files: 1→2; 실행 검사 차이 없음 (False)
- temperature_convert#separated-theme-explicit#r0 none vs rule_based: 검사 통과 변화 code_structure: False→True, style_management: False→True; 신호 files: 1→3, theme_signals: 0→7, type_signals: 7→6; 실행 검사 True→False
- temperature_convert#separated-theme-explicit#r0 rule_based vs ai_improved: 검사 통과 변화 style_management: True→False; 신호 files: 3→4, theme_signals: 7→0, type_signals: 6→7; 실행 검사 False→None
- temperature_convert#separated-theme-explicit#r0 none vs ai_improved: 검사 통과 변화 code_structure: False→True; 신호 files: 1→4; 실행 검사 True→None
- temperature_convert#separated-theme-explicit#r1 none vs rule_based: 검사 통과 변화 code_structure: False→True, style_management: False→True; 신호 files: 1→3, theme_signals: 0→13, type_signals: 5→8; 실행 검사 False→True
- temperature_convert#separated-theme-explicit#r1 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 theme_signals: 13→6, type_signals: 8→5; 실행 검사 True→False
- temperature_convert#separated-theme-explicit#r1 none vs ai_improved: 검사 통과 변화 code_structure: False→True, style_management: False→True; 신호 files: 1→3, theme_signals: 0→6; 실행 검사 차이 없음 (False)
- temperature_convert#separated-theme-explicit#r2 none vs rule_based: 검사 통과 변화 code_structure: False→True; 신호 files: 1→2; 실행 검사 True→False
- temperature_convert#separated-theme-explicit#r2 rule_based vs ai_improved: 검사 통과 변화 style_management: False→True; 신호 theme_signals: 0→13; 실행 검사 차이 없음 (False)
- temperature_convert#separated-theme-explicit#r2 none vs ai_improved: 검사 통과 변화 code_structure: False→True, style_management: False→True; 신호 files: 1→2, theme_signals: 0→13; 실행 검사 True→False
- tab_switch#compact-direct-inferred#r0 none vs rule_based: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (True)
- tab_switch#compact-direct-inferred#r0 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (True)
- tab_switch#compact-direct-inferred#r0 none vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (True)
- tab_switch#compact-direct-inferred#r1 none vs rule_based: 검사 통과 차이 없음; 신호 type_signals: 3→1; 실행 검사 차이 없음 (True)
- tab_switch#compact-direct-inferred#r1 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 type_signals: 1→3; 실행 검사 차이 없음 (True)
- tab_switch#compact-direct-inferred#r1 none vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (True)
- tab_switch#compact-direct-inferred#r2 none vs rule_based: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (True)
- tab_switch#compact-direct-inferred#r2 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (True)
- tab_switch#compact-direct-inferred#r2 none vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (True)
- char_counter#compact-direct-inferred#r0 none vs rule_based: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 4→3; 실행 검사 차이 없음 (False)
- char_counter#compact-direct-inferred#r0 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (False)
- char_counter#compact-direct-inferred#r0 none vs ai_improved: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 4→3; 실행 검사 차이 없음 (False)
- char_counter#compact-direct-inferred#r1 none vs rule_based: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 4→3; 실행 검사 차이 없음 (False)
- char_counter#compact-direct-inferred#r1 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (False)
- char_counter#compact-direct-inferred#r1 none vs ai_improved: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 4→3; 실행 검사 차이 없음 (False)
- char_counter#compact-direct-inferred#r2 none vs rule_based: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 4→3; 실행 검사 차이 없음 (False)
- char_counter#compact-direct-inferred#r2 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (False)
- char_counter#compact-direct-inferred#r2 none vs ai_improved: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 4→3; 실행 검사 차이 없음 (False)
- star_rating#compact-direct-inferred#r0 none vs rule_based: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 4→3; 실행 검사 차이 없음 (True)
- star_rating#compact-direct-inferred#r0 rule_based vs ai_improved: 검사 통과 변화 type_detail: True→False; 신호 type_signals: 3→4; 실행 검사 차이 없음 (True)
- star_rating#compact-direct-inferred#r0 none vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (True)
- star_rating#compact-direct-inferred#r1 none vs rule_based: 검사 통과 변화 code_structure: False→True; 신호 files: 2→1, type_signals: 6→4; 실행 검사 None→True
- star_rating#compact-direct-inferred#r1 rule_based vs ai_improved: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 4→3; 실행 검사 차이 없음 (True)
- star_rating#compact-direct-inferred#r1 none vs ai_improved: 검사 통과 변화 code_structure: False→True, type_detail: False→True; 신호 files: 2→1, type_signals: 6→3; 실행 검사 None→True
- star_rating#compact-direct-inferred#r2 none vs rule_based: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (True)
- star_rating#compact-direct-inferred#r2 rule_based vs ai_improved: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 4→3; 실행 검사 차이 없음 (True)
- star_rating#compact-direct-inferred#r2 none vs ai_improved: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 4→3; 실행 검사 차이 없음 (True)
- like_toggle#compact-direct-inferred#r0 none vs rule_based: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 4→2; 실행 검사 True→False
- like_toggle#compact-direct-inferred#r0 rule_based vs ai_improved: 검사 통과 변화 type_detail: True→False; 신호 type_signals: 2→4; 실행 검사 차이 없음 (False)
- like_toggle#compact-direct-inferred#r0 none vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 True→False
- like_toggle#compact-direct-inferred#r1 none vs rule_based: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 6→0; 실행 검사 차이 없음 (False)
- like_toggle#compact-direct-inferred#r1 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 type_signals: 0→2; 실행 검사 차이 없음 (False)
- like_toggle#compact-direct-inferred#r1 none vs ai_improved: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 6→2; 실행 검사 차이 없음 (False)
- like_toggle#compact-direct-inferred#r2 none vs rule_based: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 4→2; 실행 검사 차이 없음 (False)
- like_toggle#compact-direct-inferred#r2 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (False)
- like_toggle#compact-direct-inferred#r2 none vs ai_improved: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 4→2; 실행 검사 차이 없음 (False)
- temperature_convert#compact-direct-inferred#r0 none vs rule_based: 검사 통과 차이 없음; 신호 type_signals: 7→4; 실행 검사 True→False
- temperature_convert#compact-direct-inferred#r0 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (False)
- temperature_convert#compact-direct-inferred#r0 none vs ai_improved: 검사 통과 차이 없음; 신호 type_signals: 7→4; 실행 검사 True→False
- temperature_convert#compact-direct-inferred#r1 none vs rule_based: 검사 통과 차이 없음; 신호 type_signals: 5→4; 실행 검사 차이 없음 (False)
- temperature_convert#compact-direct-inferred#r1 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 type_signals: 4→5; 실행 검사 차이 없음 (False)
- temperature_convert#compact-direct-inferred#r1 none vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (False)
- temperature_convert#compact-direct-inferred#r2 none vs rule_based: 검사 통과 차이 없음; 신호 type_signals: 5→4; 실행 검사 True→False
- temperature_convert#compact-direct-inferred#r2 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (False)
- temperature_convert#compact-direct-inferred#r2 none vs ai_improved: 검사 통과 차이 없음; 신호 type_signals: 5→4; 실행 검사 True→False
- tab_switch#compact-theme-inferred#r0 none vs rule_based: 검사 통과 차이 없음; 신호 type_signals: 3→1; 실행 검사 차이 없음 (True)
- tab_switch#compact-theme-inferred#r0 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (True)
- tab_switch#compact-theme-inferred#r0 none vs ai_improved: 검사 통과 차이 없음; 신호 type_signals: 3→1; 실행 검사 차이 없음 (True)
- tab_switch#compact-theme-inferred#r1 none vs rule_based: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (True)
- tab_switch#compact-theme-inferred#r1 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 type_signals: 3→1; 실행 검사 차이 없음 (True)
- tab_switch#compact-theme-inferred#r1 none vs ai_improved: 검사 통과 차이 없음; 신호 type_signals: 3→1; 실행 검사 차이 없음 (True)
- tab_switch#compact-theme-inferred#r2 none vs rule_based: 검사 통과 변화 style_management: False→True; 신호 theme_signals: 0→13; 실행 검사 차이 없음 (True)
- tab_switch#compact-theme-inferred#r2 rule_based vs ai_improved: 검사 통과 변화 style_management: True→False; 신호 theme_signals: 13→0, type_signals: 3→1; 실행 검사 차이 없음 (True)
- tab_switch#compact-theme-inferred#r2 none vs ai_improved: 검사 통과 차이 없음; 신호 type_signals: 3→1; 실행 검사 차이 없음 (True)
- char_counter#compact-theme-inferred#r0 none vs rule_based: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 4→1; 실행 검사 차이 없음 (False)
- char_counter#compact-theme-inferred#r0 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 type_signals: 1→3; 실행 검사 차이 없음 (False)
- char_counter#compact-theme-inferred#r0 none vs ai_improved: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 4→3; 실행 검사 차이 없음 (False)
- char_counter#compact-theme-inferred#r1 none vs rule_based: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 4→1; 실행 검사 차이 없음 (False)
- char_counter#compact-theme-inferred#r1 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (False)
- char_counter#compact-theme-inferred#r1 none vs ai_improved: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 4→1; 실행 검사 차이 없음 (False)
- char_counter#compact-theme-inferred#r2 none vs rule_based: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 4→1; 실행 검사 차이 없음 (False)
- char_counter#compact-theme-inferred#r2 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 type_signals: 1→3; 실행 검사 차이 없음 (False)
- char_counter#compact-theme-inferred#r2 none vs ai_improved: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 4→3; 실행 검사 차이 없음 (False)
- star_rating#compact-theme-inferred#r0 none vs rule_based: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (True)
- star_rating#compact-theme-inferred#r0 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (True)
- star_rating#compact-theme-inferred#r0 none vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (True)
- star_rating#compact-theme-inferred#r1 none vs rule_based: 검사 통과 변화 code_structure: False→True; 신호 files: 2→1, type_signals: 6→4; 실행 검사 None→True
- star_rating#compact-theme-inferred#r1 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 True→False
- star_rating#compact-theme-inferred#r1 none vs ai_improved: 검사 통과 변화 code_structure: False→True; 신호 files: 2→1, type_signals: 6→4; 실행 검사 None→False
- star_rating#compact-theme-inferred#r2 none vs rule_based: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 4→3; 실행 검사 차이 없음 (True)
- star_rating#compact-theme-inferred#r2 rule_based vs ai_improved: 검사 통과 변화 type_detail: True→False; 신호 type_signals: 3→4; 실행 검사 True→False
- star_rating#compact-theme-inferred#r2 none vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 True→False
- like_toggle#compact-theme-inferred#r0 none vs rule_based: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 4→2; 실행 검사 True→False
- like_toggle#compact-theme-inferred#r0 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 type_signals: 2→0; 실행 검사 차이 없음 (False)
- like_toggle#compact-theme-inferred#r0 none vs ai_improved: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 4→0; 실행 검사 True→False
- like_toggle#compact-theme-inferred#r1 none vs rule_based: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 6→2; 실행 검사 차이 없음 (False)
- like_toggle#compact-theme-inferred#r1 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (False)
- like_toggle#compact-theme-inferred#r1 none vs ai_improved: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 6→2; 실행 검사 차이 없음 (False)
- like_toggle#compact-theme-inferred#r2 none vs rule_based: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 4→2; 실행 검사 차이 없음 (False)
- like_toggle#compact-theme-inferred#r2 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 type_signals: 2→0; 실행 검사 차이 없음 (False)
- like_toggle#compact-theme-inferred#r2 none vs ai_improved: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 4→0; 실행 검사 차이 없음 (False)
- temperature_convert#compact-theme-inferred#r0 none vs rule_based: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 7→2; 실행 검사 True→False
- temperature_convert#compact-theme-inferred#r0 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (False)
- temperature_convert#compact-theme-inferred#r0 none vs ai_improved: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 7→2; 실행 검사 True→False
- temperature_convert#compact-theme-inferred#r1 none vs rule_based: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 5→2; 실행 검사 차이 없음 (False)
- temperature_convert#compact-theme-inferred#r1 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (False)
- temperature_convert#compact-theme-inferred#r1 none vs ai_improved: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 5→2; 실행 검사 차이 없음 (False)
- temperature_convert#compact-theme-inferred#r2 none vs rule_based: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 True→False
- temperature_convert#compact-theme-inferred#r2 rule_based vs ai_improved: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 5→2; 실행 검사 차이 없음 (False)
- temperature_convert#compact-theme-inferred#r2 none vs ai_improved: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 5→2; 실행 검사 True→False
- tab_switch#separated-direct-explicit#r0 none vs rule_based: 검사 통과 변화 code_structure: False→True, type_detail: False→True; 신호 files: 1→2, type_signals: 3→5; 실행 검사 True→None
- tab_switch#separated-direct-explicit#r0 rule_based vs ai_improved: 검사 통과 변화 code_structure: True→False; 신호 files: 2→1; 실행 검사 None→True
- tab_switch#separated-direct-explicit#r0 none vs ai_improved: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 3→5; 실행 검사 차이 없음 (True)
- tab_switch#separated-direct-explicit#r1 none vs rule_based: 검사 통과 변화 code_structure: False→True; 신호 files: 1→2; 실행 검사 차이 없음 (True)
- tab_switch#separated-direct-explicit#r1 rule_based vs ai_improved: 검사 통과 변화 code_structure: True→False, type_detail: False→True; 신호 files: 2→1, type_signals: 3→5; 실행 검사 차이 없음 (True)
- tab_switch#separated-direct-explicit#r1 none vs ai_improved: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 3→5; 실행 검사 차이 없음 (True)
- tab_switch#separated-direct-explicit#r2 none vs rule_based: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (True)
- tab_switch#separated-direct-explicit#r2 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (True)
- tab_switch#separated-direct-explicit#r2 none vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (True)
- char_counter#separated-direct-explicit#r0 none vs rule_based: 검사 통과 변화 code_structure: False→True; 신호 files: 1→2; 실행 검사 차이 없음 (False)
- char_counter#separated-direct-explicit#r0 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (False)
- char_counter#separated-direct-explicit#r0 none vs ai_improved: 검사 통과 변화 code_structure: False→True; 신호 files: 1→2; 실행 검사 차이 없음 (False)
- char_counter#separated-direct-explicit#r1 none vs rule_based: 검사 통과 변화 code_structure: False→True; 신호 files: 1→2; 실행 검사 차이 없음 (False)
- char_counter#separated-direct-explicit#r1 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (False)
- char_counter#separated-direct-explicit#r1 none vs ai_improved: 검사 통과 변화 code_structure: False→True; 신호 files: 1→2; 실행 검사 차이 없음 (False)
- char_counter#separated-direct-explicit#r2 none vs rule_based: 검사 통과 변화 code_structure: False→True; 신호 files: 1→2; 실행 검사 차이 없음 (False)
- char_counter#separated-direct-explicit#r2 rule_based vs ai_improved: 검사 통과 변화 code_structure: True→False; 신호 files: 2→1; 실행 검사 차이 없음 (False)
- char_counter#separated-direct-explicit#r2 none vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (False)
- star_rating#separated-direct-explicit#r0 none vs rule_based: 검사 통과 변화 code_structure: False→True; 신호 files: 1→2; 실행 검사 차이 없음 (True)
- star_rating#separated-direct-explicit#r0 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (True)
- star_rating#separated-direct-explicit#r0 none vs ai_improved: 검사 통과 변화 code_structure: False→True; 신호 files: 1→2; 실행 검사 차이 없음 (True)
- star_rating#separated-direct-explicit#r1 none vs rule_based: 검사 통과 변화 type_detail: True→False; 신호 type_signals: 6→4; 실행 검사 None→True
- star_rating#separated-direct-explicit#r1 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (True)
- star_rating#separated-direct-explicit#r1 none vs ai_improved: 검사 통과 변화 type_detail: True→False; 신호 type_signals: 6→4; 실행 검사 None→True
- star_rating#separated-direct-explicit#r2 none vs rule_based: 검사 통과 변화 code_structure: False→True; 신호 files: 1→2; 실행 검사 차이 없음 (True)
- star_rating#separated-direct-explicit#r2 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (True)
- star_rating#separated-direct-explicit#r2 none vs ai_improved: 검사 통과 변화 code_structure: False→True; 신호 files: 1→2; 실행 검사 차이 없음 (True)
- like_toggle#separated-direct-explicit#r0 none vs rule_based: 검사 통과 변화 code_structure: False→True; 신호 files: 1→2; 실행 검사 True→False
- like_toggle#separated-direct-explicit#r0 rule_based vs ai_improved: 검사 통과 변화 type_detail: False→True; 신호 files: 2→3, type_signals: 4→6; 실행 검사 False→None
- like_toggle#separated-direct-explicit#r0 none vs ai_improved: 검사 통과 변화 code_structure: False→True, type_detail: False→True; 신호 files: 1→3, type_signals: 4→6; 실행 검사 True→None
- like_toggle#separated-direct-explicit#r1 none vs rule_based: 검사 통과 변화 code_structure: False→True; 신호 files: 1→2; 실행 검사 False→None
- like_toggle#separated-direct-explicit#r1 rule_based vs ai_improved: 검사 통과 변화 type_detail: True→False; 신호 type_signals: 6→4; 실행 검사 None→False
- like_toggle#separated-direct-explicit#r1 none vs ai_improved: 검사 통과 변화 code_structure: False→True, type_detail: True→False; 신호 files: 1→2, type_signals: 6→4; 실행 검사 차이 없음 (False)
- like_toggle#separated-direct-explicit#r2 none vs rule_based: 검사 통과 변화 code_structure: False→True; 신호 files: 1→2; 실행 검사 차이 없음 (False)
- like_toggle#separated-direct-explicit#r2 rule_based vs ai_improved: 검사 통과 변화 type_detail: False→True; 신호 files: 2→4, type_signals: 4→6; 실행 검사 False→None
- like_toggle#separated-direct-explicit#r2 none vs ai_improved: 검사 통과 변화 code_structure: False→True, type_detail: False→True; 신호 files: 1→4, type_signals: 4→6; 실행 검사 False→None
- temperature_convert#separated-direct-explicit#r0 none vs rule_based: 검사 통과 변화 code_structure: False→True; 신호 files: 1→2, type_signals: 7→5; 실행 검사 True→False
- temperature_convert#separated-direct-explicit#r0 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 type_signals: 5→7; 실행 검사 False→None
- temperature_convert#separated-direct-explicit#r0 none vs ai_improved: 검사 통과 변화 code_structure: False→True; 신호 files: 1→2; 실행 검사 True→None
- temperature_convert#separated-direct-explicit#r1 none vs rule_based: 검사 통과 변화 code_structure: False→True; 신호 files: 1→2; 실행 검사 차이 없음 (False)
- temperature_convert#separated-direct-explicit#r1 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 files: 2→4, type_signals: 5→9; 실행 검사 False→None
- temperature_convert#separated-direct-explicit#r1 none vs ai_improved: 검사 통과 변화 code_structure: False→True; 신호 files: 1→4, type_signals: 5→9; 실행 검사 False→None
- temperature_convert#separated-direct-explicit#r2 none vs rule_based: 검사 통과 변화 code_structure: False→True; 신호 files: 1→2, type_signals: 5→7; 실행 검사 True→False
- temperature_convert#separated-direct-explicit#r2 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 type_signals: 7→9; 실행 검사 False→None
- temperature_convert#separated-direct-explicit#r2 none vs ai_improved: 검사 통과 변화 code_structure: False→True; 신호 files: 1→2, type_signals: 5→9; 실행 검사 True→None
