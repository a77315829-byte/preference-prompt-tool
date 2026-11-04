# 개인화 프롬프트 3조건 비교

- 생성: 2026-11-03T01:30:46.942872+00:00 · 모드: `execute` · 모델: `openai/gpt-4o-mini` · 언어: `ko`
- 목표 선호(가상 사용자): `{"code_structure": "separated", "style_management": "theme", "type_detail": "explicit"}`
- 개선 단계: `ai_improved`
- 새 API 요청: 생성 1회, 개선 1회 · 토큰(공급자 보고, 청구서 아님) 입력 1957 / 출력 662 · 경과 14.93초
- 주의: Static style checks only. Passing them does not show functional equivalence, runtime correctness or user satisfaction. With few tasks, differences are anecdotes.

| 과제 | 조건 | 파일 구성 | 스타일 관리 | 타입 작성 | 스타일 전부 | 파일 수 | 테마 신호 | 타입 신호 | 품질 문제 | 타입 검사 | 빌드 | 동작 시나리오 | 기능 통과(독립) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| counter_reset | none | ❌ 0.5 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 5 | 3 | 미실행 | 미실행 | 미실행 | 미실행 |
| counter_reset | rule_based | ✅ 1.0 | ✅ 1.0 | ❌ 0.6 | 아니오 | 2 | 19 | 3 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| counter_reset | ai_improved | ✅ 1.0 | ❌ 0.0 | ❌ 0.8 | 아니오 | 2 | 0 | 4 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |

## 조건 간 차이

- counter_reset none vs rule_based: 검사 통과 변화 code_structure: False→True, style_management: False→True, type_detail: True→False; 신호 files: 1→2, theme_signals: 0→19, type_signals: 5→3
- counter_reset rule_based vs ai_improved: 검사 통과 변화 style_management: True→False; 신호 theme_signals: 19→0, type_signals: 3→4
- counter_reset none vs ai_improved: 검사 통과 변화 code_structure: False→True, type_detail: True→False; 신호 files: 1→2, type_signals: 5→4
