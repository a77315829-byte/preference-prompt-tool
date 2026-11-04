# 개인화 프롬프트 3조건 비교

- 생성: 2026-11-03T02:05:46.129466+00:00 · 모드: `cached-only` · 모델: `openai/gpt-4o-mini` · 언어: `ko` · split `calibration` · 반복 1 · temperature 0.0
- 목표 선호 `{"code_structure": "separated", "style_management": "theme", "type_detail": "explicit"}` → 개선 단계 `replayed` · (c) 출처 `ai_improved`
- 새 API 요청: 생성 0회, 개선 0회 · 토큰(공급자 보고, 청구서 아님) 입력 0 / 출력 0 · 경과 3.15초
- 주의: Style checks are static. The independent behavior check covers only the task's frozen acceptance scenario; neither shows functional equivalence on all inputs or user satisfaction. With few tasks, differences are anecdotes.

| 과제 | 조건 | 파일 구성 | 스타일 관리 | 타입 작성 | 스타일 전부 | 파일 수 | 테마 신호 | 타입 신호 | 품질 문제 | 타입 검사 | 빌드 | 동작 시나리오 | 기능 통과(독립) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| counter_reset | none | ❌ 0.5 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 5 | 3 | ✅ | ✅ | passed (3/3) | ✅ |
| counter_reset | rule_based | ✅ 1.0 | ✅ 1.0 | ❌ 0.6 | 아니오 | 2 | 19 | 3 | 1 | ✅ | ✅ | passed (3/3) | ✅ |
| counter_reset | ai_improved | ✅ 1.0 | ❌ 0.0 | ❌ 0.8 | 아니오 | 2 | 0 | 4 | 2 | ✅ | ✅ | passed (3/3) | ✅ |

## 집계

| 조건 | 출력 | 누락 | 축 통과율 | 세 축 전부 | 기능 통과율 | 기능 미확인 |
|---|---|---|---|---|---|---|
| none | 1 | 0 | 0.3333 | 0.0 | 1.0 | 0 |
| rule_based | 1 | 0 | 0.6667 | 0.0 | 1.0 | 0 |
| ai_improved | 1 | 0 | 0.3333 | 0.0 | 1.0 | 0 |

| 짝 비교 | 단위 수 | 축 통과율 차이 [95% 구간] | 기능 통과율 차이 [95% 구간] |
|---|---|---|---|
| ai_improved-rule_based | 1 | -0.3333 (-0.3333, -0.3333) | 0.0 (0.0, 0.0) |
| rule_based-none | 1 | 0.3333 (0.3333, 0.3333) | 0.0 (0.0, 0.0) |

- 사전등록 기준 (판정에 쓰지 않는다 (pilot·재생·calibration)): {"style_gain": false, "functional_non_inferior": true, "fallback_rate": false} → 전부 충족: `False` · 미적용 비율 1.0

## 조건 간 차이

- counter_reset none vs rule_based: 검사 통과 변화 code_structure: False→True, style_management: False→True, type_detail: True→False; 신호 files: 1→2, theme_signals: 0→19, type_signals: 5→3; 실행 검사 차이 없음 (True)
- counter_reset rule_based vs ai_improved: 검사 통과 변화 style_management: True→False; 신호 theme_signals: 19→0, type_signals: 3→4; 실행 검사 차이 없음 (True)
- counter_reset none vs ai_improved: 검사 통과 변화 code_structure: False→True, type_detail: True→False; 신호 files: 1→2, type_signals: 5→4; 실행 검사 차이 없음 (True)
