# 개인화 프롬프트 3조건 비교

- 생성: 2026-11-03T07:47:32.639362+00:00 · 모드: `cached-only` · 모델: `openai/gpt-4o-mini` · 언어: `ko` · split `calibration` · 반복 1 · temperature 0.7
- 목표 선호 `{"code_structure": "separated", "style_management": "theme", "type_detail": "explicit"}` → 개선 단계 `ai_improved` · (c) 출처 `ai_improved`
- 목표 선호 `{"code_structure": "compact", "style_management": "direct", "type_detail": "inferred"}` → 개선 단계 `ai_improved` · (c) 출처 `ai_improved`
- 목표 선호 `{"code_structure": "compact", "style_management": "theme", "type_detail": "inferred"}` → 개선 단계 `fallback` (reason `limit_reached`) · (b) 와 문구 같음 · (c) 출처 `fallback_base`
- 목표 선호 `{"code_structure": "separated", "style_management": "direct", "type_detail": "explicit"}` → 개선 단계 `ai_improved` · (c) 출처 `ai_improved`
- 새 API 요청: 생성 0회, 개선 0회 · 토큰(공급자 보고, 청구서 아님) 입력 0 / 출력 0 · 경과 66.7초
- 주의: Style checks are static. The independent behavior check covers only the task's frozen acceptance scenario; neither shows functional equivalence on all inputs or user satisfaction. With few tasks, differences are anecdotes.

| 과제 | 조건 | 파일 구성 | 스타일 관리 | 타입 작성 | 스타일 전부 | 파일 수 | 테마 신호 | 타입 신호 | 품질 문제 | 타입 검사 | 빌드 | 동작 시나리오 | 기능 통과(독립) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| counter_reset · separated-theme-explicit · r0 | none | ❌ 0.5 | ❌ 0.0 | ❌ 0.6 | 아니오 | 1 | 0 | 3 | 3 | ✅ | ✅ | passed (3/3) | ✅ |
| counter_reset · separated-theme-explicit · r0 | rule_based | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 2 | 11 | 5 | 0 | ❌ | ❌ | not_run | ❌ |
| counter_reset · separated-theme-explicit · r0 | ai_improved | ✅ 1.0 | ❌ 0.0 | ❌ 0.6 | 아니오 | 2 | 0 | 3 | 3 | ✅ | ✅ | passed (3/3) | ✅ |
| product_search · separated-theme-explicit · r0 | none | ❌ 0.5 | ❌ 0.0 | ❌ 0.6 | 아니오 | 1 | 0 | 3 | 3 | ✅ | ✅ | passed (3/3) | ✅ |
| product_search · separated-theme-explicit · r0 | rule_based | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 3 | 0 | 8 | 1 | ❌ | ❌ | not_run | ❌ |
| product_search · separated-theme-explicit · r0 | ai_improved | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 4 | 0 | 13 | 1 | ✅ | ✅ | passed (3/3) | ✅ |
| signup_validation · separated-theme-explicit · r0 | none | ❌ 0.5 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 12 | 2 | ✅ | ✅ | failed (1/3) | ❌ |
| signup_validation · separated-theme-explicit · r0 | rule_based | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 2 | 10 | 15 | 0 | ✅ | ✅ | passed (3/3) | ✅ |
| signup_validation · separated-theme-explicit · r0 | ai_improved | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 2 | 0 | 7 | 1 | ❌ | ❌ | not_run | ❌ |
| todo_toggle · separated-theme-explicit · r0 | none | ❌ 0.5 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 8 | 2 | ✅ | ✅ | passed (3/3) | ✅ |
| todo_toggle · separated-theme-explicit · r0 | rule_based | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 4 | 11 | 14 | 0 | ❌ | ❌ | not_run | ❌ |
| todo_toggle · separated-theme-explicit · r0 | ai_improved | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 3 | 12 | 12 | 1 | ✅ | ✅ | passed (3/3) | ✅ |
| counter_reset · compact-direct-inferred · r0 | none | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 3 | 1 | ✅ | ✅ | passed (3/3) | ✅ |
| counter_reset · compact-direct-inferred · r0 | rule_based | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 2 | 1 | ✅ | ✅ | passed (3/3) | ✅ |
| counter_reset · compact-direct-inferred · r0 | ai_improved | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 2 | 1 | ✅ | ✅ | passed (3/3) | ✅ |
| product_search · compact-direct-inferred · r0 | none | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 3 | 1 | ✅ | ✅ | passed (3/3) | ✅ |
| product_search · compact-direct-inferred · r0 | rule_based | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 3 | 1 | ✅ | ✅ | passed (3/3) | ✅ |
| product_search · compact-direct-inferred · r0 | ai_improved | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 2 | 1 | ✅ | ✅ | passed (3/3) | ✅ |
| signup_validation · compact-direct-inferred · r0 | none | ✅ 1.0 | ✅ 1.0 | ❌ 0.25 | 아니오 | 1 | 0 | 12 | 1 | ✅ | ✅ | failed (1/3) | ❌ |
| signup_validation · compact-direct-inferred · r0 | rule_based | ✅ 1.0 | ✅ 1.0 | ❌ 0.429 | 아니오 | 1 | 0 | 7 | 1 | ✅ | ✅ | failed (1/3) | ❌ |
| signup_validation · compact-direct-inferred · r0 | ai_improved | ✅ 1.0 | ✅ 1.0 | ❌ 0.5 | 아니오 | 1 | 0 | 6 | 1 | ✅ | ✅ | passed (3/3) | ✅ |
| todo_toggle · compact-direct-inferred · r0 | none | ✅ 1.0 | ✅ 1.0 | ❌ 0.375 | 아니오 | 1 | 0 | 8 | 1 | ✅ | ✅ | passed (3/3) | ✅ |
| todo_toggle · compact-direct-inferred · r0 | rule_based | ✅ 1.0 | ✅ 1.0 | ❌ 0.5 | 아니오 | 1 | 0 | 6 | 1 | ✅ | ✅ | passed (3/3) | ✅ |
| todo_toggle · compact-direct-inferred · r0 | ai_improved | ✅ 1.0 | ✅ 1.0 | ❌ 0.5 | 아니오 | 1 | 0 | 6 | 1 | ✅ | ✅ | passed (3/3) | ✅ |
| counter_reset · compact-theme-inferred · r0 | none | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 3 | 2 | ✅ | ✅ | passed (3/3) | ✅ |
| counter_reset · compact-theme-inferred · r0 | rule_based | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 2 | 2 | ✅ | ✅ | passed (3/3) | ✅ |
| counter_reset · compact-theme-inferred · r0 | ai_improved | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 2 | 2 | ✅ | ✅ | passed (3/3) | ✅ |
| product_search · compact-theme-inferred · r0 | none | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 3 | 2 | ✅ | ✅ | passed (3/3) | ✅ |
| product_search · compact-theme-inferred · r0 | rule_based | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 3 | 2 | ✅ | ✅ | passed (3/3) | ✅ |
| product_search · compact-theme-inferred · r0 | ai_improved | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 3 | 2 | ✅ | ✅ | passed (3/3) | ✅ |
| signup_validation · compact-theme-inferred · r0 | none | ✅ 1.0 | ❌ 0.0 | ❌ 0.25 | 아니오 | 1 | 0 | 12 | 2 | ✅ | ✅ | failed (1/3) | ❌ |
| signup_validation · compact-theme-inferred · r0 | rule_based | ✅ 1.0 | ❌ 0.0 | ❌ 0.75 | 아니오 | 1 | 0 | 4 | 1 | ✅ | ✅ | passed (3/3) | ✅ |
| signup_validation · compact-theme-inferred · r0 | ai_improved | ✅ 1.0 | ❌ 0.0 | ❌ 0.75 | 아니오 | 1 | 0 | 4 | 1 | ✅ | ✅ | passed (3/3) | ✅ |
| todo_toggle · compact-theme-inferred · r0 | none | ✅ 1.0 | ❌ 0.0 | ❌ 0.375 | 아니오 | 1 | 0 | 8 | 2 | ✅ | ✅ | passed (3/3) | ✅ |
| todo_toggle · compact-theme-inferred · r0 | rule_based | ✅ 1.0 | ✅ 1.0 | ❌ 0.375 | 아니오 | 1 | 5 | 8 | 1 | ✅ | ✅ | passed (3/3) | ✅ |
| todo_toggle · compact-theme-inferred · r0 | ai_improved | ✅ 1.0 | ✅ 1.0 | ❌ 0.375 | 아니오 | 1 | 5 | 8 | 1 | ✅ | ✅ | passed (3/3) | ✅ |
| counter_reset · separated-direct-explicit · r0 | none | ❌ 0.5 | ✅ 1.0 | ❌ 0.6 | 아니오 | 1 | 0 | 3 | 2 | ✅ | ✅ | passed (3/3) | ✅ |
| counter_reset · separated-direct-explicit · r0 | rule_based | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 4 | 0 | 5 | 2 | ✅ | ✅ | passed (3/3) | ✅ |
| counter_reset · separated-direct-explicit · r0 | ai_improved | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 2 | 0 | 5 | 0 | ✅ | ✅ | passed (3/3) | ✅ |
| product_search · separated-direct-explicit · r0 | none | ❌ 0.5 | ✅ 1.0 | ❌ 0.6 | 아니오 | 1 | 0 | 3 | 2 | ✅ | ✅ | passed (3/3) | ✅ |
| product_search · separated-direct-explicit · r0 | rule_based | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 2 | 0 | 5 | 0 | ✅ | ✅ | passed (3/3) | ✅ |
| product_search · separated-direct-explicit · r0 | ai_improved | ❌ 0.5 | ✅ 1.0 | ✅ 1.0 | 아니오 | 1 | 0 | 9 | 1 | ✅ | ✅ | passed (3/3) | ✅ |
| signup_validation · separated-direct-explicit · r0 | none | ❌ 0.5 | ✅ 1.0 | ✅ 1.0 | 아니오 | 1 | 0 | 12 | 1 | ✅ | ✅ | failed (1/3) | ❌ |
| signup_validation · separated-direct-explicit · r0 | rule_based | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 2 | 0 | 8 | 0 | ✅ | ✅ | failed (1/3) | ❌ |
| signup_validation · separated-direct-explicit · r0 | ai_improved | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 2 | 0 | 9 | 0 | ✅ | ✅ | failed (1/3) | ❌ |
| todo_toggle · separated-direct-explicit · r0 | none | ❌ 0.5 | ✅ 1.0 | ✅ 1.0 | 아니오 | 1 | 0 | 8 | 1 | ✅ | ✅ | passed (3/3) | ✅ |
| todo_toggle · separated-direct-explicit · r0 | rule_based | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 2 | 0 | 11 | 0 | ✅ | ✅ | passed (3/3) | ✅ |
| todo_toggle · separated-direct-explicit · r0 | ai_improved | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 2 | 0 | 9 | 1 | ✅ | ✅ | passed (3/3) | ✅ |

## 집계

| 조건 | 출력 | 누락 | 축 통과율 | 세 축 전부 | 기능 통과율 | 기능 미확인 |
|---|---|---|---|---|---|---|
| none | 16 | 0 | 0.5 | 0.125 | 0.75 | 0 |
| rule_based | 16 | 0 | 0.8333 | 0.5625 | 0.6875 | 0 |
| ai_improved | 16 | 0 | 0.75 | 0.375 | 0.875 | 0 |

| 짝 비교 | 단위 수 | 축 통과율 차이 [95% 구간] | 기능 통과율 차이 [95% 구간] |
|---|---|---|---|
| ai_improved-rule_based | 16 | -0.0833 (-0.1875, 0.0) | 0.1875 (-0.0625, 0.4375) |
| rule_based-none | 16 | 0.3333 (0.1667, 0.5) | -0.0625 (-0.3125, 0.1875) |

- 사전등록 기준 (판정에 쓰지 않는다 (pilot·재생·calibration)): {"style_gain": false, "functional_non_inferior": true, "fallback_rate": true} → 전부 충족: `False` · 미적용 비율 0.25

## 조건 간 차이

- counter_reset#separated-theme-explicit#r0 none vs rule_based: 검사 통과 변화 code_structure: False→True, style_management: False→True, type_detail: False→True; 신호 files: 1→2, theme_signals: 0→11, type_signals: 3→5; 실행 검사 True→False
- counter_reset#separated-theme-explicit#r0 rule_based vs ai_improved: 검사 통과 변화 style_management: True→False, type_detail: True→False; 신호 theme_signals: 11→0, type_signals: 5→3; 실행 검사 False→True
- counter_reset#separated-theme-explicit#r0 none vs ai_improved: 검사 통과 변화 code_structure: False→True; 신호 files: 1→2; 실행 검사 차이 없음 (True)
- product_search#separated-theme-explicit#r0 none vs rule_based: 검사 통과 변화 code_structure: False→True, type_detail: False→True; 신호 files: 1→3, type_signals: 3→8; 실행 검사 True→False
- product_search#separated-theme-explicit#r0 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 files: 3→4, type_signals: 8→13; 실행 검사 False→True
- product_search#separated-theme-explicit#r0 none vs ai_improved: 검사 통과 변화 code_structure: False→True, type_detail: False→True; 신호 files: 1→4, type_signals: 3→13; 실행 검사 차이 없음 (True)
- signup_validation#separated-theme-explicit#r0 none vs rule_based: 검사 통과 변화 code_structure: False→True, style_management: False→True; 신호 files: 1→2, theme_signals: 0→10, type_signals: 12→15; 실행 검사 False→True
- signup_validation#separated-theme-explicit#r0 rule_based vs ai_improved: 검사 통과 변화 style_management: True→False; 신호 theme_signals: 10→0, type_signals: 15→7; 실행 검사 True→False
- signup_validation#separated-theme-explicit#r0 none vs ai_improved: 검사 통과 변화 code_structure: False→True; 신호 files: 1→2, type_signals: 12→7; 실행 검사 차이 없음 (False)
- todo_toggle#separated-theme-explicit#r0 none vs rule_based: 검사 통과 변화 code_structure: False→True, style_management: False→True; 신호 files: 1→4, theme_signals: 0→11, type_signals: 8→14; 실행 검사 True→False
- todo_toggle#separated-theme-explicit#r0 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 files: 4→3, theme_signals: 11→12, type_signals: 14→12; 실행 검사 False→True
- todo_toggle#separated-theme-explicit#r0 none vs ai_improved: 검사 통과 변화 code_structure: False→True, style_management: False→True; 신호 files: 1→3, theme_signals: 0→12, type_signals: 8→12; 실행 검사 차이 없음 (True)
- counter_reset#compact-direct-inferred#r0 none vs rule_based: 검사 통과 차이 없음; 신호 type_signals: 3→2; 실행 검사 차이 없음 (True)
- counter_reset#compact-direct-inferred#r0 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (True)
- counter_reset#compact-direct-inferred#r0 none vs ai_improved: 검사 통과 차이 없음; 신호 type_signals: 3→2; 실행 검사 차이 없음 (True)
- product_search#compact-direct-inferred#r0 none vs rule_based: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (True)
- product_search#compact-direct-inferred#r0 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 type_signals: 3→2; 실행 검사 차이 없음 (True)
- product_search#compact-direct-inferred#r0 none vs ai_improved: 검사 통과 차이 없음; 신호 type_signals: 3→2; 실행 검사 차이 없음 (True)
- signup_validation#compact-direct-inferred#r0 none vs rule_based: 검사 통과 차이 없음; 신호 type_signals: 12→7; 실행 검사 차이 없음 (False)
- signup_validation#compact-direct-inferred#r0 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 type_signals: 7→6; 실행 검사 False→True
- signup_validation#compact-direct-inferred#r0 none vs ai_improved: 검사 통과 차이 없음; 신호 type_signals: 12→6; 실행 검사 False→True
- todo_toggle#compact-direct-inferred#r0 none vs rule_based: 검사 통과 차이 없음; 신호 type_signals: 8→6; 실행 검사 차이 없음 (True)
- todo_toggle#compact-direct-inferred#r0 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (True)
- todo_toggle#compact-direct-inferred#r0 none vs ai_improved: 검사 통과 차이 없음; 신호 type_signals: 8→6; 실행 검사 차이 없음 (True)
- counter_reset#compact-theme-inferred#r0 none vs rule_based: 검사 통과 차이 없음; 신호 type_signals: 3→2; 실행 검사 차이 없음 (True)
- counter_reset#compact-theme-inferred#r0 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (True)
- counter_reset#compact-theme-inferred#r0 none vs ai_improved: 검사 통과 차이 없음; 신호 type_signals: 3→2; 실행 검사 차이 없음 (True)
- product_search#compact-theme-inferred#r0 none vs rule_based: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (True)
- product_search#compact-theme-inferred#r0 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (True)
- product_search#compact-theme-inferred#r0 none vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (True)
- signup_validation#compact-theme-inferred#r0 none vs rule_based: 검사 통과 차이 없음; 신호 type_signals: 12→4; 실행 검사 False→True
- signup_validation#compact-theme-inferred#r0 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (True)
- signup_validation#compact-theme-inferred#r0 none vs ai_improved: 검사 통과 차이 없음; 신호 type_signals: 12→4; 실행 검사 False→True
- todo_toggle#compact-theme-inferred#r0 none vs rule_based: 검사 통과 변화 style_management: False→True; 신호 theme_signals: 0→5; 실행 검사 차이 없음 (True)
- todo_toggle#compact-theme-inferred#r0 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (True)
- todo_toggle#compact-theme-inferred#r0 none vs ai_improved: 검사 통과 변화 style_management: False→True; 신호 theme_signals: 0→5; 실행 검사 차이 없음 (True)
- counter_reset#separated-direct-explicit#r0 none vs rule_based: 검사 통과 변화 code_structure: False→True, type_detail: False→True; 신호 files: 1→4, type_signals: 3→5; 실행 검사 차이 없음 (True)
- counter_reset#separated-direct-explicit#r0 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 files: 4→2; 실행 검사 차이 없음 (True)
- counter_reset#separated-direct-explicit#r0 none vs ai_improved: 검사 통과 변화 code_structure: False→True, type_detail: False→True; 신호 files: 1→2, type_signals: 3→5; 실행 검사 차이 없음 (True)
- product_search#separated-direct-explicit#r0 none vs rule_based: 검사 통과 변화 code_structure: False→True, type_detail: False→True; 신호 files: 1→2, type_signals: 3→5; 실행 검사 차이 없음 (True)
- product_search#separated-direct-explicit#r0 rule_based vs ai_improved: 검사 통과 변화 code_structure: True→False; 신호 files: 2→1, type_signals: 5→9; 실행 검사 차이 없음 (True)
- product_search#separated-direct-explicit#r0 none vs ai_improved: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 3→9; 실행 검사 차이 없음 (True)
- signup_validation#separated-direct-explicit#r0 none vs rule_based: 검사 통과 변화 code_structure: False→True; 신호 files: 1→2, type_signals: 12→8; 실행 검사 차이 없음 (False)
- signup_validation#separated-direct-explicit#r0 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 type_signals: 8→9; 실행 검사 차이 없음 (False)
- signup_validation#separated-direct-explicit#r0 none vs ai_improved: 검사 통과 변화 code_structure: False→True; 신호 files: 1→2, type_signals: 12→9; 실행 검사 차이 없음 (False)
- todo_toggle#separated-direct-explicit#r0 none vs rule_based: 검사 통과 변화 code_structure: False→True; 신호 files: 1→2, type_signals: 8→11; 실행 검사 차이 없음 (True)
- todo_toggle#separated-direct-explicit#r0 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 type_signals: 11→9; 실행 검사 차이 없음 (True)
- todo_toggle#separated-direct-explicit#r0 none vs ai_improved: 검사 통과 변화 code_structure: False→True; 신호 files: 1→2, type_signals: 8→9; 실행 검사 차이 없음 (True)
