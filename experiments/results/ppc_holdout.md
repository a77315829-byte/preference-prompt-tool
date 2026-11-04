# 개인화 프롬프트 3조건 비교

- 생성: 2026-11-03T02:33:54.916884+00:00 · 모드: `execute` · 모델: `openai/gpt-4o-mini` · 언어: `ko` · split `holdout` · 반복 3 · temperature 0.7
- 목표 선호 `{"code_structure": "separated", "style_management": "theme", "type_detail": "explicit"}` → 개선 단계 `ai_improved` · (c) 출처 `ai_improved`
- 목표 선호 `{"code_structure": "compact", "style_management": "direct", "type_detail": "inferred"}` → 개선 단계 `ai_improved` · (c) 출처 `ai_improved`
- 목표 선호 `{"code_structure": "compact", "style_management": "theme", "type_detail": "inferred"}` → 개선 단계 `ai_improved` · (c) 출처 `ai_improved`
- 목표 선호 `{"code_structure": "separated", "style_management": "direct", "type_detail": "explicit"}` → 개선 단계 `ai_improved` · (c) 출처 `ai_improved`
- 새 API 요청: 생성 1회, 개선 0회 · 토큰(공급자 보고, 청구서 아님) 입력 849 / 출력 408 · 경과 8.99초
- 주의: Style checks are static. The independent behavior check covers only the task's frozen acceptance scenario; neither shows functional equivalence on all inputs or user satisfaction. With few tasks, differences are anecdotes.

| 과제 | 조건 | 파일 구성 | 스타일 관리 | 타입 작성 | 스타일 전부 | 파일 수 | 테마 신호 | 타입 신호 | 품질 문제 | 타입 검사 | 빌드 | 동작 시나리오 | 기능 통과(독립) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| confirm_dialog · separated-theme-explicit · r0 | none | ❌ 0.5 | ❌ 0.0 | ❌ 0.8 | 아니오 | 1 | 0 | 4 | 3 | 미실행 | 미실행 | 미실행 | 미실행 |
| confirm_dialog · separated-theme-explicit · r0 | rule_based | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 3 | 0 | 8 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| confirm_dialog · separated-theme-explicit · r0 | ai_improved | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 2 | 0 | 8 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| confirm_dialog · separated-theme-explicit · r1 | none | ❌ 0.5 | ❌ 0.0 | ❌ 0.6 | 아니오 | 1 | 0 | 3 | 3 | 미실행 | 미실행 | 미실행 | 미실행 |
| confirm_dialog · separated-theme-explicit · r1 | rule_based | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 2 | 0 | 6 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| confirm_dialog · separated-theme-explicit · r1 | ai_improved | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 3 | 8 | 6 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| confirm_dialog · separated-theme-explicit · r2 | none | ❌ 0.5 | ❌ 0.0 | ❌ 0.4 | 아니오 | 1 | 0 | 2 | 3 | 미실행 | 미실행 | 미실행 | 미실행 |
| confirm_dialog · separated-theme-explicit · r2 | rule_based | ✅ 1.0 | ✅ 1.0 | ❌ 0.4 | 아니오 | 2 | 18 | 2 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| confirm_dialog · separated-theme-explicit · r2 | ai_improved | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 3 | 6 | 8 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| text_preview · separated-theme-explicit · r0 | none | ❌ 0.5 | ❌ 0.0 | ❌ 0.8 | 아니오 | 1 | 0 | 4 | 3 | 미실행 | 미실행 | 미실행 | 미실행 |
| text_preview · separated-theme-explicit · r0 | rule_based | ✅ 1.0 | ❌ 0.0 | ❌ 0.8 | 아니오 | 2 | 0 | 4 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| text_preview · separated-theme-explicit · r0 | ai_improved | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 2 | 0 | 6 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| text_preview · separated-theme-explicit · r1 | none | ❌ 0.5 | ❌ 0.0 | ❌ 0.8 | 아니오 | 1 | 0 | 4 | 3 | 미실행 | 미실행 | 미실행 | 미실행 |
| text_preview · separated-theme-explicit · r1 | rule_based | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 2 | 0 | 5 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| text_preview · separated-theme-explicit · r1 | ai_improved | ❌ 0.5 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 5 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| text_preview · separated-theme-explicit · r2 | none | ❌ 0.5 | ❌ 0.0 | ❌ 0.8 | 아니오 | 1 | 0 | 4 | 3 | 미실행 | 미실행 | 미실행 | 미실행 |
| text_preview · separated-theme-explicit · r2 | rule_based | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 2 | 0 | 6 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| text_preview · separated-theme-explicit · r2 | ai_improved | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 2 | 0 | 5 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| password_visibility · separated-theme-explicit · r0 | none | ❌ 0.5 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 5 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| password_visibility · separated-theme-explicit · r0 | rule_based | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 4 | 0 | 6 | 3 | 미실행 | 미실행 | 미실행 | 미실행 |
| password_visibility · separated-theme-explicit · r0 | ai_improved | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 3 | 0 | 9 | 3 | 미실행 | 미실행 | 미실행 | 미실행 |
| password_visibility · separated-theme-explicit · r1 | none | ❌ 0.5 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 5 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| password_visibility · separated-theme-explicit · r1 | rule_based | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 2 | 0 | 7 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| password_visibility · separated-theme-explicit · r1 | ai_improved | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 3 | 0 | 7 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| password_visibility · separated-theme-explicit · r2 | none | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 2 | 0 | 6 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| password_visibility · separated-theme-explicit · r2 | rule_based | ✅ 1.0 | ❌ 0.0 | ❌ 0.8 | 아니오 | 2 | 0 | 4 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| password_visibility · separated-theme-explicit · r2 | ai_improved | ❌ 0.5 | ❌ 0.0 | ❌ 0.8 | 아니오 | 1 | 0 | 4 | 3 | 미실행 | 미실행 | 미실행 | 미실행 |
| faq_toggle · separated-theme-explicit · r0 | none | ❌ 0.5 | ❌ 0.0 | ❌ 0.4 | 아니오 | 1 | 0 | 2 | 3 | 미실행 | 미실행 | 미실행 | 미실행 |
| faq_toggle · separated-theme-explicit · r0 | rule_based | ✅ 1.0 | ❌ 0.0 | ❌ 0.6 | 아니오 | 2 | 0 | 3 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| faq_toggle · separated-theme-explicit · r0 | ai_improved | ❌ 0.5 | ❌ 0.0 | ❌ 0.6 | 아니오 | 1 | 0 | 3 | 3 | 미실행 | 미실행 | 미실행 | 미실행 |
| faq_toggle · separated-theme-explicit · r1 | none | ❌ 0.5 | ❌ 0.0 | ❌ 0.4 | 아니오 | 1 | 0 | 2 | 3 | 미실행 | 미실행 | 미실행 | 미실행 |
| faq_toggle · separated-theme-explicit · r1 | rule_based | ✅ 1.0 | ✅ 1.0 | ❌ 0.6 | 아니오 | 2 | 15 | 3 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| faq_toggle · separated-theme-explicit · r1 | ai_improved | ❌ 0.5 | ❌ 0.0 | ❌ 0.6 | 아니오 | 1 | 0 | 3 | 3 | 미실행 | 미실행 | 미실행 | 미실행 |
| faq_toggle · separated-theme-explicit · r2 | none | ❌ 0.5 | ❌ 0.0 | ❌ 0.4 | 아니오 | 1 | 0 | 2 | 3 | 미실행 | 미실행 | 미실행 | 미실행 |
| faq_toggle · separated-theme-explicit · r2 | rule_based | ❌ 0.5 | ❌ 0.0 | ❌ 0.6 | 아니오 | 1 | 0 | 3 | 3 | 미실행 | 미실행 | 미실행 | 미실행 |
| faq_toggle · separated-theme-explicit · r2 | ai_improved | ✅ 1.0 | ❌ 0.0 | ❌ 0.8 | 아니오 | 2 | 0 | 4 | 3 | 미실행 | 미실행 | 미실행 | 미실행 |
| cart_quantity · separated-theme-explicit · r0 | none | ❌ 0.5 | ❌ 0.0 | ❌ 0.6 | 아니오 | 1 | 0 | 3 | 3 | 미실행 | 미실행 | 미실행 | 미실행 |
| cart_quantity · separated-theme-explicit · r0 | rule_based | ✅ 1.0 | ❌ 0.0 | ❌ 0.8 | 아니오 | 2 | 0 | 4 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| cart_quantity · separated-theme-explicit · r0 | ai_improved | ✅ 1.0 | ❌ 0.0 | ❌ 0.6 | 아니오 | 2 | 0 | 3 | 3 | 미실행 | 미실행 | 미실행 | 미실행 |
| cart_quantity · separated-theme-explicit · r1 | none | ❌ 0.5 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 5 | 3 | 미실행 | 미실행 | 미실행 | 미실행 |
| cart_quantity · separated-theme-explicit · r1 | rule_based | ✅ 1.0 | ✅ 1.0 | ❌ 0.6 | 아니오 | 2 | 8 | 3 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| cart_quantity · separated-theme-explicit · r1 | ai_improved | ✅ 1.0 | ❌ 0.0 | ❌ 0.8 | 아니오 | 2 | 0 | 4 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| cart_quantity · separated-theme-explicit · r2 | none | ❌ 0.5 | ❌ 0.0 | ❌ 0.6 | 아니오 | 1 | 0 | 3 | 3 | 미실행 | 미실행 | 미실행 | 미실행 |
| cart_quantity · separated-theme-explicit · r2 | rule_based | ✅ 1.0 | ❌ 0.0 | ❌ 0.6 | 아니오 | 2 | 0 | 3 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| cart_quantity · separated-theme-explicit · r2 | ai_improved | ✅ 1.0 | ❌ 0.0 | ❌ 0.6 | 아니오 | 2 | 0 | 3 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| confirm_dialog · compact-direct-inferred · r0 | none | ✅ 1.0 | ✅ 1.0 | ❌ 0.75 | 아니오 | 1 | 0 | 4 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| confirm_dialog · compact-direct-inferred · r0 | rule_based | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 3 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| confirm_dialog · compact-direct-inferred · r0 | ai_improved | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 2 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| confirm_dialog · compact-direct-inferred · r1 | none | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 3 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| confirm_dialog · compact-direct-inferred · r1 | rule_based | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 2 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| confirm_dialog · compact-direct-inferred · r1 | ai_improved | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 3 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| confirm_dialog · compact-direct-inferred · r2 | none | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 2 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| confirm_dialog · compact-direct-inferred · r2 | rule_based | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 2 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| confirm_dialog · compact-direct-inferred · r2 | ai_improved | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 2 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| text_preview · compact-direct-inferred · r0 | none | ✅ 1.0 | ✅ 1.0 | ❌ 0.75 | 아니오 | 1 | 0 | 4 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| text_preview · compact-direct-inferred · r0 | rule_based | ✅ 1.0 | ✅ 1.0 | ❌ 0.75 | 아니오 | 1 | 0 | 4 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| text_preview · compact-direct-inferred · r0 | ai_improved | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 3 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| text_preview · compact-direct-inferred · r1 | none | ✅ 1.0 | ✅ 1.0 | ❌ 0.75 | 아니오 | 1 | 0 | 4 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| text_preview · compact-direct-inferred · r1 | rule_based | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 3 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| text_preview · compact-direct-inferred · r1 | ai_improved | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 3 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| text_preview · compact-direct-inferred · r2 | none | ✅ 1.0 | ✅ 1.0 | ❌ 0.75 | 아니오 | 1 | 0 | 4 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| text_preview · compact-direct-inferred · r2 | rule_based | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 3 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| text_preview · compact-direct-inferred · r2 | ai_improved | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 3 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| password_visibility · compact-direct-inferred · r0 | none | ✅ 1.0 | ✅ 1.0 | ❌ 0.6 | 아니오 | 1 | 0 | 5 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| password_visibility · compact-direct-inferred · r0 | rule_based | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 2 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| password_visibility · compact-direct-inferred · r0 | ai_improved | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 2 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| password_visibility · compact-direct-inferred · r1 | none | ✅ 1.0 | ✅ 1.0 | ❌ 0.6 | 아니오 | 1 | 0 | 5 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| password_visibility · compact-direct-inferred · r1 | rule_based | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 2 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| password_visibility · compact-direct-inferred · r1 | ai_improved | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 2 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| password_visibility · compact-direct-inferred · r2 | none | ❌ 0.5 | ✅ 1.0 | ❌ 0.5 | 아니오 | 2 | 0 | 6 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| password_visibility · compact-direct-inferred · r2 | rule_based | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 2 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| password_visibility · compact-direct-inferred · r2 | ai_improved | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 2 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| faq_toggle · compact-direct-inferred · r0 | none | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 2 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| faq_toggle · compact-direct-inferred · r0 | rule_based | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 2 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| faq_toggle · compact-direct-inferred · r0 | ai_improved | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 2 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| faq_toggle · compact-direct-inferred · r1 | none | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 2 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| faq_toggle · compact-direct-inferred · r1 | rule_based | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 2 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| faq_toggle · compact-direct-inferred · r1 | ai_improved | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 2 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| faq_toggle · compact-direct-inferred · r2 | none | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 2 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| faq_toggle · compact-direct-inferred · r2 | rule_based | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 2 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| faq_toggle · compact-direct-inferred · r2 | ai_improved | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 2 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| cart_quantity · compact-direct-inferred · r0 | none | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 3 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| cart_quantity · compact-direct-inferred · r0 | rule_based | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 0 | 0 | 미실행 | 미실행 | 미실행 | 미실행 |
| cart_quantity · compact-direct-inferred · r0 | ai_improved | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 0 | 0 | 미실행 | 미실행 | 미실행 | 미실행 |
| cart_quantity · compact-direct-inferred · r1 | none | ✅ 1.0 | ✅ 1.0 | ❌ 0.6 | 아니오 | 1 | 0 | 5 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| cart_quantity · compact-direct-inferred · r1 | rule_based | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 2 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| cart_quantity · compact-direct-inferred · r1 | ai_improved | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 0 | 0 | 미실행 | 미실행 | 미실행 | 미실행 |
| cart_quantity · compact-direct-inferred · r2 | none | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 3 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| cart_quantity · compact-direct-inferred · r2 | rule_based | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 2 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| cart_quantity · compact-direct-inferred · r2 | ai_improved | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 0 | 0 | 0 | 미실행 | 미실행 | 미실행 | 미실행 |
| confirm_dialog · compact-theme-inferred · r0 | none | ✅ 1.0 | ❌ 0.0 | ❌ 0.75 | 아니오 | 1 | 0 | 4 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| confirm_dialog · compact-theme-inferred · r0 | rule_based | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 22 | 2 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| confirm_dialog · compact-theme-inferred · r0 | ai_improved | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 2 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| confirm_dialog · compact-theme-inferred · r1 | none | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 3 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| confirm_dialog · compact-theme-inferred · r1 | rule_based | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 2 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| confirm_dialog · compact-theme-inferred · r1 | ai_improved | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 17 | 2 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| confirm_dialog · compact-theme-inferred · r2 | none | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 2 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| confirm_dialog · compact-theme-inferred · r2 | rule_based | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 1 | 17 | 2 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| confirm_dialog · compact-theme-inferred · r2 | ai_improved | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 2 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| text_preview · compact-theme-inferred · r0 | none | ✅ 1.0 | ❌ 0.0 | ❌ 0.75 | 아니오 | 1 | 0 | 4 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| text_preview · compact-theme-inferred · r0 | rule_based | ✅ 1.0 | ❌ 0.0 | ❌ 0.75 | 아니오 | 1 | 0 | 4 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| text_preview · compact-theme-inferred · r0 | ai_improved | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 3 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| text_preview · compact-theme-inferred · r1 | none | ✅ 1.0 | ❌ 0.0 | ❌ 0.75 | 아니오 | 1 | 0 | 4 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| text_preview · compact-theme-inferred · r1 | rule_based | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 3 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| text_preview · compact-theme-inferred · r1 | ai_improved | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 3 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| text_preview · compact-theme-inferred · r2 | none | ✅ 1.0 | ❌ 0.0 | ❌ 0.75 | 아니오 | 1 | 0 | 4 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| text_preview · compact-theme-inferred · r2 | rule_based | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 3 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| text_preview · compact-theme-inferred · r2 | ai_improved | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 3 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| password_visibility · compact-theme-inferred · r0 | none | ✅ 1.0 | ❌ 0.0 | ❌ 0.6 | 아니오 | 1 | 0 | 5 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| password_visibility · compact-theme-inferred · r0 | rule_based | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 2 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| password_visibility · compact-theme-inferred · r0 | ai_improved | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 2 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| password_visibility · compact-theme-inferred · r1 | none | ✅ 1.0 | ❌ 0.0 | ❌ 0.6 | 아니오 | 1 | 0 | 5 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| password_visibility · compact-theme-inferred · r1 | rule_based | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 2 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| password_visibility · compact-theme-inferred · r1 | ai_improved | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 2 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| password_visibility · compact-theme-inferred · r2 | none | ❌ 0.5 | ❌ 0.0 | ❌ 0.5 | 아니오 | 2 | 0 | 6 | 3 | 미실행 | 미실행 | 미실행 | 미실행 |
| password_visibility · compact-theme-inferred · r2 | rule_based | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 2 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| password_visibility · compact-theme-inferred · r2 | ai_improved | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 2 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| faq_toggle · compact-theme-inferred · r0 | none | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 2 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| faq_toggle · compact-theme-inferred · r0 | rule_based | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 2 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| faq_toggle · compact-theme-inferred · r0 | ai_improved | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 2 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| faq_toggle · compact-theme-inferred · r1 | none | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 2 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| faq_toggle · compact-theme-inferred · r1 | rule_based | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 2 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| faq_toggle · compact-theme-inferred · r1 | ai_improved | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 2 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| faq_toggle · compact-theme-inferred · r2 | none | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 2 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| faq_toggle · compact-theme-inferred · r2 | rule_based | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 2 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| faq_toggle · compact-theme-inferred · r2 | ai_improved | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 2 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| cart_quantity · compact-theme-inferred · r0 | none | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 3 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| cart_quantity · compact-theme-inferred · r0 | rule_based | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 2 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| cart_quantity · compact-theme-inferred · r0 | ai_improved | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 2 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| cart_quantity · compact-theme-inferred · r1 | none | ✅ 1.0 | ❌ 0.0 | ❌ 0.6 | 아니오 | 1 | 0 | 5 | 3 | 미실행 | 미실행 | 미실행 | 미실행 |
| cart_quantity · compact-theme-inferred · r1 | rule_based | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 0 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| cart_quantity · compact-theme-inferred · r1 | ai_improved | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 2 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| cart_quantity · compact-theme-inferred · r2 | none | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 3 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| cart_quantity · compact-theme-inferred · r2 | rule_based | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 2 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| cart_quantity · compact-theme-inferred · r2 | ai_improved | ✅ 1.0 | ❌ 0.0 | ✅ 1.0 | 아니오 | 1 | 0 | 2 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| confirm_dialog · separated-direct-explicit · r0 | none | ❌ 0.5 | ✅ 1.0 | ❌ 0.8 | 아니오 | 1 | 0 | 4 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| confirm_dialog · separated-direct-explicit · r0 | rule_based | ✅ 1.0 | ✅ 1.0 | ❌ 0.8 | 아니오 | 2 | 0 | 4 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| confirm_dialog · separated-direct-explicit · r0 | ai_improved | ❌ 0.5 | ✅ 1.0 | ❌ 0.8 | 아니오 | 1 | 0 | 4 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| confirm_dialog · separated-direct-explicit · r1 | none | ❌ 0.5 | ✅ 1.0 | ❌ 0.6 | 아니오 | 1 | 0 | 3 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| confirm_dialog · separated-direct-explicit · r1 | rule_based | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 3 | 0 | 7 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| confirm_dialog · separated-direct-explicit · r1 | ai_improved | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 2 | 0 | 6 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| confirm_dialog · separated-direct-explicit · r2 | none | ❌ 0.5 | ✅ 1.0 | ❌ 0.4 | 아니오 | 1 | 0 | 2 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| confirm_dialog · separated-direct-explicit · r2 | rule_based | ✅ 1.0 | ✅ 1.0 | ❌ 0.8 | 아니오 | 2 | 0 | 4 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| confirm_dialog · separated-direct-explicit · r2 | ai_improved | ❌ 0.5 | ✅ 1.0 | ✅ 1.0 | 아니오 | 1 | 0 | 6 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| text_preview · separated-direct-explicit · r0 | none | ❌ 0.5 | ✅ 1.0 | ❌ 0.8 | 아니오 | 1 | 0 | 4 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| text_preview · separated-direct-explicit · r0 | rule_based | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 2 | 0 | 5 | 0 | 미실행 | 미실행 | 미실행 | 미실행 |
| text_preview · separated-direct-explicit · r0 | ai_improved | ❌ 0.5 | ✅ 1.0 | ✅ 1.0 | 아니오 | 1 | 0 | 5 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| text_preview · separated-direct-explicit · r1 | none | ❌ 0.5 | ✅ 1.0 | ❌ 0.8 | 아니오 | 1 | 0 | 4 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| text_preview · separated-direct-explicit · r1 | rule_based | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 2 | 0 | 5 | 0 | 미실행 | 미실행 | 미실행 | 미실행 |
| text_preview · separated-direct-explicit · r1 | ai_improved | ❌ 0.5 | ✅ 1.0 | ✅ 1.0 | 아니오 | 1 | 0 | 5 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| text_preview · separated-direct-explicit · r2 | none | ❌ 0.5 | ✅ 1.0 | ❌ 0.8 | 아니오 | 1 | 0 | 4 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| text_preview · separated-direct-explicit · r2 | rule_based | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 2 | 0 | 5 | 0 | 미실행 | 미실행 | 미실행 | 미실행 |
| text_preview · separated-direct-explicit · r2 | ai_improved | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 2 | 0 | 5 | 0 | 미실행 | 미실행 | 미실행 | 미실행 |
| password_visibility · separated-direct-explicit · r0 | none | ❌ 0.5 | ✅ 1.0 | ✅ 1.0 | 아니오 | 1 | 0 | 5 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| password_visibility · separated-direct-explicit · r0 | rule_based | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 2 | 0 | 6 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| password_visibility · separated-direct-explicit · r0 | ai_improved | ❌ 0.5 | ✅ 1.0 | ❌ 0.8 | 아니오 | 1 | 0 | 4 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| password_visibility · separated-direct-explicit · r1 | none | ❌ 0.5 | ✅ 1.0 | ✅ 1.0 | 아니오 | 1 | 0 | 5 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| password_visibility · separated-direct-explicit · r1 | rule_based | ❌ 0.5 | ✅ 1.0 | ❌ 0.8 | 아니오 | 1 | 0 | 4 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| password_visibility · separated-direct-explicit · r1 | ai_improved | ❌ 0.5 | ✅ 1.0 | ❌ 0.8 | 아니오 | 1 | 0 | 4 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| password_visibility · separated-direct-explicit · r2 | none | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 2 | 0 | 6 | 0 | 미실행 | 미실행 | 미실행 | 미실행 |
| password_visibility · separated-direct-explicit · r2 | rule_based | ✅ 1.0 | ✅ 1.0 | ❌ 0.8 | 아니오 | 2 | 0 | 4 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| password_visibility · separated-direct-explicit · r2 | ai_improved | ❌ 0.5 | ✅ 1.0 | ✅ 1.0 | 아니오 | 1 | 0 | 5 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| faq_toggle · separated-direct-explicit · r0 | none | ❌ 0.5 | ✅ 1.0 | ❌ 0.4 | 아니오 | 1 | 0 | 2 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| faq_toggle · separated-direct-explicit · r0 | rule_based | ✅ 1.0 | ✅ 1.0 | ❌ 0.6 | 아니오 | 2 | 0 | 3 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| faq_toggle · separated-direct-explicit · r0 | ai_improved | ❌ 0.5 | ✅ 1.0 | ❌ 0.6 | 아니오 | 1 | 0 | 3 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| faq_toggle · separated-direct-explicit · r1 | none | ❌ 0.5 | ✅ 1.0 | ❌ 0.4 | 아니오 | 1 | 0 | 2 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| faq_toggle · separated-direct-explicit · r1 | rule_based | ✅ 1.0 | ✅ 1.0 | ❌ 0.6 | 아니오 | 2 | 0 | 3 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| faq_toggle · separated-direct-explicit · r1 | ai_improved | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 3 | 0 | 5 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| faq_toggle · separated-direct-explicit · r2 | none | ❌ 0.5 | ✅ 1.0 | ❌ 0.4 | 아니오 | 1 | 0 | 2 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| faq_toggle · separated-direct-explicit · r2 | rule_based | ✅ 1.0 | ✅ 1.0 | ❌ 0.6 | 아니오 | 2 | 0 | 3 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| faq_toggle · separated-direct-explicit · r2 | ai_improved | ❌ 0.5 | ✅ 1.0 | ❌ 0.6 | 아니오 | 1 | 0 | 3 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| cart_quantity · separated-direct-explicit · r0 | none | ❌ 0.5 | ✅ 1.0 | ❌ 0.6 | 아니오 | 1 | 0 | 3 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| cart_quantity · separated-direct-explicit · r0 | rule_based | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 3 | 0 | 5 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| cart_quantity · separated-direct-explicit · r0 | ai_improved | ❌ 0.5 | ✅ 1.0 | ✅ 1.0 | 아니오 | 1 | 0 | 5 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| cart_quantity · separated-direct-explicit · r1 | none | ❌ 0.5 | ✅ 1.0 | ✅ 1.0 | 아니오 | 1 | 0 | 5 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| cart_quantity · separated-direct-explicit · r1 | rule_based | ✅ 1.0 | ✅ 1.0 | ❌ 0.6 | 아니오 | 2 | 0 | 3 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| cart_quantity · separated-direct-explicit · r1 | ai_improved | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 3 | 0 | 5 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| cart_quantity · separated-direct-explicit · r2 | none | ❌ 0.5 | ✅ 1.0 | ❌ 0.6 | 아니오 | 1 | 0 | 3 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |
| cart_quantity · separated-direct-explicit · r2 | rule_based | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 2 | 0 | 9 | 1 | 미실행 | 미실행 | 미실행 | 미실행 |
| cart_quantity · separated-direct-explicit · r2 | ai_improved | ✅ 1.0 | ✅ 1.0 | ✅ 1.0 | 예 | 4 | 0 | 8 | 2 | 미실행 | 미실행 | 미실행 | 미실행 |

## 집계

| 조건 | 출력 | 누락 | 축 통과율 | 세 축 전부 | 기능 통과율 | 기능 미확인 |
|---|---|---|---|---|---|---|
| none | 60 | 0 | 0.4556 | 0.1333 | None | None |
| rule_based | 60 | 0 | 0.7444 | 0.3833 | None | None |
| ai_improved | 60 | 0 | 0.7056 | 0.3833 | None | None |

| 짝 비교 | 단위 수 | 축 통과율 차이 [95% 구간] | 기능 통과율 차이 [95% 구간] |
|---|---|---|---|
| ai_improved-rule_based | 60 | -0.0389 [-0.0944, 0.0167] | None None |
| rule_based-none | 60 | 0.2889 [0.2222, 0.3611] | None None |

- 사전등록 기준 (확증(판정에 쓴다)): {"style_gain": false, "functional_non_inferior": null, "fallback_rate": true} → 전부 충족: `None` · 미적용 비율 0.0

## 조건 간 차이

- confirm_dialog#separated-theme-explicit#r0 none vs rule_based: 검사 통과 변화 code_structure: False→True, type_detail: False→True; 신호 files: 1→3, type_signals: 4→8; 실행 검사 차이 없음 (not_run)
- confirm_dialog#separated-theme-explicit#r0 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 files: 3→2; 실행 검사 차이 없음 (not_run)
- confirm_dialog#separated-theme-explicit#r0 none vs ai_improved: 검사 통과 변화 code_structure: False→True, type_detail: False→True; 신호 files: 1→2, type_signals: 4→8; 실행 검사 차이 없음 (not_run)
- confirm_dialog#separated-theme-explicit#r1 none vs rule_based: 검사 통과 변화 code_structure: False→True, type_detail: False→True; 신호 files: 1→2, type_signals: 3→6; 실행 검사 차이 없음 (not_run)
- confirm_dialog#separated-theme-explicit#r1 rule_based vs ai_improved: 검사 통과 변화 style_management: False→True; 신호 files: 2→3, theme_signals: 0→8; 실행 검사 차이 없음 (not_run)
- confirm_dialog#separated-theme-explicit#r1 none vs ai_improved: 검사 통과 변화 code_structure: False→True, style_management: False→True, type_detail: False→True; 신호 files: 1→3, theme_signals: 0→8, type_signals: 3→6; 실행 검사 차이 없음 (not_run)
- confirm_dialog#separated-theme-explicit#r2 none vs rule_based: 검사 통과 변화 code_structure: False→True, style_management: False→True; 신호 files: 1→2, theme_signals: 0→18; 실행 검사 차이 없음 (not_run)
- confirm_dialog#separated-theme-explicit#r2 rule_based vs ai_improved: 검사 통과 변화 type_detail: False→True; 신호 files: 2→3, theme_signals: 18→6, type_signals: 2→8; 실행 검사 차이 없음 (not_run)
- confirm_dialog#separated-theme-explicit#r2 none vs ai_improved: 검사 통과 변화 code_structure: False→True, style_management: False→True, type_detail: False→True; 신호 files: 1→3, theme_signals: 0→6, type_signals: 2→8; 실행 검사 차이 없음 (not_run)
- text_preview#separated-theme-explicit#r0 none vs rule_based: 검사 통과 변화 code_structure: False→True; 신호 files: 1→2; 실행 검사 차이 없음 (not_run)
- text_preview#separated-theme-explicit#r0 rule_based vs ai_improved: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 4→6; 실행 검사 차이 없음 (not_run)
- text_preview#separated-theme-explicit#r0 none vs ai_improved: 검사 통과 변화 code_structure: False→True, type_detail: False→True; 신호 files: 1→2, type_signals: 4→6; 실행 검사 차이 없음 (not_run)
- text_preview#separated-theme-explicit#r1 none vs rule_based: 검사 통과 변화 code_structure: False→True, type_detail: False→True; 신호 files: 1→2, type_signals: 4→5; 실행 검사 차이 없음 (not_run)
- text_preview#separated-theme-explicit#r1 rule_based vs ai_improved: 검사 통과 변화 code_structure: True→False; 신호 files: 2→1; 실행 검사 차이 없음 (not_run)
- text_preview#separated-theme-explicit#r1 none vs ai_improved: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 4→5; 실행 검사 차이 없음 (not_run)
- text_preview#separated-theme-explicit#r2 none vs rule_based: 검사 통과 변화 code_structure: False→True, type_detail: False→True; 신호 files: 1→2, type_signals: 4→6; 실행 검사 차이 없음 (not_run)
- text_preview#separated-theme-explicit#r2 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 type_signals: 6→5; 실행 검사 차이 없음 (not_run)
- text_preview#separated-theme-explicit#r2 none vs ai_improved: 검사 통과 변화 code_structure: False→True, type_detail: False→True; 신호 files: 1→2, type_signals: 4→5; 실행 검사 차이 없음 (not_run)
- password_visibility#separated-theme-explicit#r0 none vs rule_based: 검사 통과 변화 code_structure: False→True; 신호 files: 1→4, type_signals: 5→6; 실행 검사 차이 없음 (not_run)
- password_visibility#separated-theme-explicit#r0 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 files: 4→3, type_signals: 6→9; 실행 검사 차이 없음 (not_run)
- password_visibility#separated-theme-explicit#r0 none vs ai_improved: 검사 통과 변화 code_structure: False→True; 신호 files: 1→3, type_signals: 5→9; 실행 검사 차이 없음 (not_run)
- password_visibility#separated-theme-explicit#r1 none vs rule_based: 검사 통과 변화 code_structure: False→True; 신호 files: 1→2, type_signals: 5→7; 실행 검사 차이 없음 (not_run)
- password_visibility#separated-theme-explicit#r1 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 files: 2→3; 실행 검사 차이 없음 (not_run)
- password_visibility#separated-theme-explicit#r1 none vs ai_improved: 검사 통과 변화 code_structure: False→True; 신호 files: 1→3, type_signals: 5→7; 실행 검사 차이 없음 (not_run)
- password_visibility#separated-theme-explicit#r2 none vs rule_based: 검사 통과 변화 type_detail: True→False; 신호 type_signals: 6→4; 실행 검사 차이 없음 (not_run)
- password_visibility#separated-theme-explicit#r2 rule_based vs ai_improved: 검사 통과 변화 code_structure: True→False; 신호 files: 2→1; 실행 검사 차이 없음 (not_run)
- password_visibility#separated-theme-explicit#r2 none vs ai_improved: 검사 통과 변화 code_structure: True→False, type_detail: True→False; 신호 files: 2→1, type_signals: 6→4; 실행 검사 차이 없음 (not_run)
- faq_toggle#separated-theme-explicit#r0 none vs rule_based: 검사 통과 변화 code_structure: False→True; 신호 files: 1→2, type_signals: 2→3; 실행 검사 차이 없음 (not_run)
- faq_toggle#separated-theme-explicit#r0 rule_based vs ai_improved: 검사 통과 변화 code_structure: True→False; 신호 files: 2→1; 실행 검사 차이 없음 (not_run)
- faq_toggle#separated-theme-explicit#r0 none vs ai_improved: 검사 통과 차이 없음; 신호 type_signals: 2→3; 실행 검사 차이 없음 (not_run)
- faq_toggle#separated-theme-explicit#r1 none vs rule_based: 검사 통과 변화 code_structure: False→True, style_management: False→True; 신호 files: 1→2, theme_signals: 0→15, type_signals: 2→3; 실행 검사 차이 없음 (not_run)
- faq_toggle#separated-theme-explicit#r1 rule_based vs ai_improved: 검사 통과 변화 code_structure: True→False, style_management: True→False; 신호 files: 2→1, theme_signals: 15→0; 실행 검사 차이 없음 (not_run)
- faq_toggle#separated-theme-explicit#r1 none vs ai_improved: 검사 통과 차이 없음; 신호 type_signals: 2→3; 실행 검사 차이 없음 (not_run)
- faq_toggle#separated-theme-explicit#r2 none vs rule_based: 검사 통과 차이 없음; 신호 type_signals: 2→3; 실행 검사 차이 없음 (not_run)
- faq_toggle#separated-theme-explicit#r2 rule_based vs ai_improved: 검사 통과 변화 code_structure: False→True; 신호 files: 1→2, type_signals: 3→4; 실행 검사 차이 없음 (not_run)
- faq_toggle#separated-theme-explicit#r2 none vs ai_improved: 검사 통과 변화 code_structure: False→True; 신호 files: 1→2, type_signals: 2→4; 실행 검사 차이 없음 (not_run)
- cart_quantity#separated-theme-explicit#r0 none vs rule_based: 검사 통과 변화 code_structure: False→True; 신호 files: 1→2, type_signals: 3→4; 실행 검사 차이 없음 (not_run)
- cart_quantity#separated-theme-explicit#r0 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 type_signals: 4→3; 실행 검사 차이 없음 (not_run)
- cart_quantity#separated-theme-explicit#r0 none vs ai_improved: 검사 통과 변화 code_structure: False→True; 신호 files: 1→2; 실행 검사 차이 없음 (not_run)
- cart_quantity#separated-theme-explicit#r1 none vs rule_based: 검사 통과 변화 code_structure: False→True, style_management: False→True, type_detail: True→False; 신호 files: 1→2, theme_signals: 0→8, type_signals: 5→3; 실행 검사 차이 없음 (not_run)
- cart_quantity#separated-theme-explicit#r1 rule_based vs ai_improved: 검사 통과 변화 style_management: True→False; 신호 theme_signals: 8→0, type_signals: 3→4; 실행 검사 차이 없음 (not_run)
- cart_quantity#separated-theme-explicit#r1 none vs ai_improved: 검사 통과 변화 code_structure: False→True, type_detail: True→False; 신호 files: 1→2, type_signals: 5→4; 실행 검사 차이 없음 (not_run)
- cart_quantity#separated-theme-explicit#r2 none vs rule_based: 검사 통과 변화 code_structure: False→True; 신호 files: 1→2; 실행 검사 차이 없음 (not_run)
- cart_quantity#separated-theme-explicit#r2 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (not_run)
- cart_quantity#separated-theme-explicit#r2 none vs ai_improved: 검사 통과 변화 code_structure: False→True; 신호 files: 1→2; 실행 검사 차이 없음 (not_run)
- confirm_dialog#compact-direct-inferred#r0 none vs rule_based: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 4→3; 실행 검사 차이 없음 (not_run)
- confirm_dialog#compact-direct-inferred#r0 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 type_signals: 3→2; 실행 검사 차이 없음 (not_run)
- confirm_dialog#compact-direct-inferred#r0 none vs ai_improved: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 4→2; 실행 검사 차이 없음 (not_run)
- confirm_dialog#compact-direct-inferred#r1 none vs rule_based: 검사 통과 차이 없음; 신호 type_signals: 3→2; 실행 검사 차이 없음 (not_run)
- confirm_dialog#compact-direct-inferred#r1 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 type_signals: 2→3; 실행 검사 차이 없음 (not_run)
- confirm_dialog#compact-direct-inferred#r1 none vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (not_run)
- confirm_dialog#compact-direct-inferred#r2 none vs rule_based: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (not_run)
- confirm_dialog#compact-direct-inferred#r2 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (not_run)
- confirm_dialog#compact-direct-inferred#r2 none vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (not_run)
- text_preview#compact-direct-inferred#r0 none vs rule_based: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (not_run)
- text_preview#compact-direct-inferred#r0 rule_based vs ai_improved: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 4→3; 실행 검사 차이 없음 (not_run)
- text_preview#compact-direct-inferred#r0 none vs ai_improved: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 4→3; 실행 검사 차이 없음 (not_run)
- text_preview#compact-direct-inferred#r1 none vs rule_based: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 4→3; 실행 검사 차이 없음 (not_run)
- text_preview#compact-direct-inferred#r1 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (not_run)
- text_preview#compact-direct-inferred#r1 none vs ai_improved: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 4→3; 실행 검사 차이 없음 (not_run)
- text_preview#compact-direct-inferred#r2 none vs rule_based: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 4→3; 실행 검사 차이 없음 (not_run)
- text_preview#compact-direct-inferred#r2 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (not_run)
- text_preview#compact-direct-inferred#r2 none vs ai_improved: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 4→3; 실행 검사 차이 없음 (not_run)
- password_visibility#compact-direct-inferred#r0 none vs rule_based: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 5→2; 실행 검사 차이 없음 (not_run)
- password_visibility#compact-direct-inferred#r0 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (not_run)
- password_visibility#compact-direct-inferred#r0 none vs ai_improved: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 5→2; 실행 검사 차이 없음 (not_run)
- password_visibility#compact-direct-inferred#r1 none vs rule_based: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 5→2; 실행 검사 차이 없음 (not_run)
- password_visibility#compact-direct-inferred#r1 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (not_run)
- password_visibility#compact-direct-inferred#r1 none vs ai_improved: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 5→2; 실행 검사 차이 없음 (not_run)
- password_visibility#compact-direct-inferred#r2 none vs rule_based: 검사 통과 변화 code_structure: False→True, type_detail: False→True; 신호 files: 2→1, type_signals: 6→2; 실행 검사 차이 없음 (not_run)
- password_visibility#compact-direct-inferred#r2 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (not_run)
- password_visibility#compact-direct-inferred#r2 none vs ai_improved: 검사 통과 변화 code_structure: False→True, type_detail: False→True; 신호 files: 2→1, type_signals: 6→2; 실행 검사 차이 없음 (not_run)
- faq_toggle#compact-direct-inferred#r0 none vs rule_based: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (not_run)
- faq_toggle#compact-direct-inferred#r0 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (not_run)
- faq_toggle#compact-direct-inferred#r0 none vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (not_run)
- faq_toggle#compact-direct-inferred#r1 none vs rule_based: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (not_run)
- faq_toggle#compact-direct-inferred#r1 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (not_run)
- faq_toggle#compact-direct-inferred#r1 none vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (not_run)
- faq_toggle#compact-direct-inferred#r2 none vs rule_based: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (not_run)
- faq_toggle#compact-direct-inferred#r2 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (not_run)
- faq_toggle#compact-direct-inferred#r2 none vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (not_run)
- cart_quantity#compact-direct-inferred#r0 none vs rule_based: 검사 통과 차이 없음; 신호 type_signals: 3→0; 실행 검사 차이 없음 (not_run)
- cart_quantity#compact-direct-inferred#r0 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (not_run)
- cart_quantity#compact-direct-inferred#r0 none vs ai_improved: 검사 통과 차이 없음; 신호 type_signals: 3→0; 실행 검사 차이 없음 (not_run)
- cart_quantity#compact-direct-inferred#r1 none vs rule_based: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 5→2; 실행 검사 차이 없음 (not_run)
- cart_quantity#compact-direct-inferred#r1 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 type_signals: 2→0; 실행 검사 차이 없음 (not_run)
- cart_quantity#compact-direct-inferred#r1 none vs ai_improved: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 5→0; 실행 검사 차이 없음 (not_run)
- cart_quantity#compact-direct-inferred#r2 none vs rule_based: 검사 통과 차이 없음; 신호 type_signals: 3→2; 실행 검사 차이 없음 (not_run)
- cart_quantity#compact-direct-inferred#r2 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 type_signals: 2→0; 실행 검사 차이 없음 (not_run)
- cart_quantity#compact-direct-inferred#r2 none vs ai_improved: 검사 통과 차이 없음; 신호 type_signals: 3→0; 실행 검사 차이 없음 (not_run)
- confirm_dialog#compact-theme-inferred#r0 none vs rule_based: 검사 통과 변화 style_management: False→True, type_detail: False→True; 신호 theme_signals: 0→22, type_signals: 4→2; 실행 검사 차이 없음 (not_run)
- confirm_dialog#compact-theme-inferred#r0 rule_based vs ai_improved: 검사 통과 변화 style_management: True→False; 신호 theme_signals: 22→0; 실행 검사 차이 없음 (not_run)
- confirm_dialog#compact-theme-inferred#r0 none vs ai_improved: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 4→2; 실행 검사 차이 없음 (not_run)
- confirm_dialog#compact-theme-inferred#r1 none vs rule_based: 검사 통과 차이 없음; 신호 type_signals: 3→2; 실행 검사 차이 없음 (not_run)
- confirm_dialog#compact-theme-inferred#r1 rule_based vs ai_improved: 검사 통과 변화 style_management: False→True; 신호 theme_signals: 0→17; 실행 검사 차이 없음 (not_run)
- confirm_dialog#compact-theme-inferred#r1 none vs ai_improved: 검사 통과 변화 style_management: False→True; 신호 theme_signals: 0→17, type_signals: 3→2; 실행 검사 차이 없음 (not_run)
- confirm_dialog#compact-theme-inferred#r2 none vs rule_based: 검사 통과 변화 style_management: False→True; 신호 theme_signals: 0→17; 실행 검사 차이 없음 (not_run)
- confirm_dialog#compact-theme-inferred#r2 rule_based vs ai_improved: 검사 통과 변화 style_management: True→False; 신호 theme_signals: 17→0; 실행 검사 차이 없음 (not_run)
- confirm_dialog#compact-theme-inferred#r2 none vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (not_run)
- text_preview#compact-theme-inferred#r0 none vs rule_based: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (not_run)
- text_preview#compact-theme-inferred#r0 rule_based vs ai_improved: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 4→3; 실행 검사 차이 없음 (not_run)
- text_preview#compact-theme-inferred#r0 none vs ai_improved: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 4→3; 실행 검사 차이 없음 (not_run)
- text_preview#compact-theme-inferred#r1 none vs rule_based: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 4→3; 실행 검사 차이 없음 (not_run)
- text_preview#compact-theme-inferred#r1 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (not_run)
- text_preview#compact-theme-inferred#r1 none vs ai_improved: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 4→3; 실행 검사 차이 없음 (not_run)
- text_preview#compact-theme-inferred#r2 none vs rule_based: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 4→3; 실행 검사 차이 없음 (not_run)
- text_preview#compact-theme-inferred#r2 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (not_run)
- text_preview#compact-theme-inferred#r2 none vs ai_improved: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 4→3; 실행 검사 차이 없음 (not_run)
- password_visibility#compact-theme-inferred#r0 none vs rule_based: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 5→2; 실행 검사 차이 없음 (not_run)
- password_visibility#compact-theme-inferred#r0 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (not_run)
- password_visibility#compact-theme-inferred#r0 none vs ai_improved: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 5→2; 실행 검사 차이 없음 (not_run)
- password_visibility#compact-theme-inferred#r1 none vs rule_based: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 5→2; 실행 검사 차이 없음 (not_run)
- password_visibility#compact-theme-inferred#r1 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (not_run)
- password_visibility#compact-theme-inferred#r1 none vs ai_improved: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 5→2; 실행 검사 차이 없음 (not_run)
- password_visibility#compact-theme-inferred#r2 none vs rule_based: 검사 통과 변화 code_structure: False→True, type_detail: False→True; 신호 files: 2→1, type_signals: 6→2; 실행 검사 차이 없음 (not_run)
- password_visibility#compact-theme-inferred#r2 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (not_run)
- password_visibility#compact-theme-inferred#r2 none vs ai_improved: 검사 통과 변화 code_structure: False→True, type_detail: False→True; 신호 files: 2→1, type_signals: 6→2; 실행 검사 차이 없음 (not_run)
- faq_toggle#compact-theme-inferred#r0 none vs rule_based: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (not_run)
- faq_toggle#compact-theme-inferred#r0 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (not_run)
- faq_toggle#compact-theme-inferred#r0 none vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (not_run)
- faq_toggle#compact-theme-inferred#r1 none vs rule_based: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (not_run)
- faq_toggle#compact-theme-inferred#r1 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (not_run)
- faq_toggle#compact-theme-inferred#r1 none vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (not_run)
- faq_toggle#compact-theme-inferred#r2 none vs rule_based: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (not_run)
- faq_toggle#compact-theme-inferred#r2 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (not_run)
- faq_toggle#compact-theme-inferred#r2 none vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (not_run)
- cart_quantity#compact-theme-inferred#r0 none vs rule_based: 검사 통과 차이 없음; 신호 type_signals: 3→2; 실행 검사 차이 없음 (not_run)
- cart_quantity#compact-theme-inferred#r0 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (not_run)
- cart_quantity#compact-theme-inferred#r0 none vs ai_improved: 검사 통과 차이 없음; 신호 type_signals: 3→2; 실행 검사 차이 없음 (not_run)
- cart_quantity#compact-theme-inferred#r1 none vs rule_based: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 5→0; 실행 검사 차이 없음 (not_run)
- cart_quantity#compact-theme-inferred#r1 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 type_signals: 0→2; 실행 검사 차이 없음 (not_run)
- cart_quantity#compact-theme-inferred#r1 none vs ai_improved: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 5→2; 실행 검사 차이 없음 (not_run)
- cart_quantity#compact-theme-inferred#r2 none vs rule_based: 검사 통과 차이 없음; 신호 type_signals: 3→2; 실행 검사 차이 없음 (not_run)
- cart_quantity#compact-theme-inferred#r2 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (not_run)
- cart_quantity#compact-theme-inferred#r2 none vs ai_improved: 검사 통과 차이 없음; 신호 type_signals: 3→2; 실행 검사 차이 없음 (not_run)
- confirm_dialog#separated-direct-explicit#r0 none vs rule_based: 검사 통과 변화 code_structure: False→True; 신호 files: 1→2; 실행 검사 차이 없음 (not_run)
- confirm_dialog#separated-direct-explicit#r0 rule_based vs ai_improved: 검사 통과 변화 code_structure: True→False; 신호 files: 2→1; 실행 검사 차이 없음 (not_run)
- confirm_dialog#separated-direct-explicit#r0 none vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (not_run)
- confirm_dialog#separated-direct-explicit#r1 none vs rule_based: 검사 통과 변화 code_structure: False→True, type_detail: False→True; 신호 files: 1→3, type_signals: 3→7; 실행 검사 차이 없음 (not_run)
- confirm_dialog#separated-direct-explicit#r1 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 files: 3→2, type_signals: 7→6; 실행 검사 차이 없음 (not_run)
- confirm_dialog#separated-direct-explicit#r1 none vs ai_improved: 검사 통과 변화 code_structure: False→True, type_detail: False→True; 신호 files: 1→2, type_signals: 3→6; 실행 검사 차이 없음 (not_run)
- confirm_dialog#separated-direct-explicit#r2 none vs rule_based: 검사 통과 변화 code_structure: False→True; 신호 files: 1→2, type_signals: 2→4; 실행 검사 차이 없음 (not_run)
- confirm_dialog#separated-direct-explicit#r2 rule_based vs ai_improved: 검사 통과 변화 code_structure: True→False, type_detail: False→True; 신호 files: 2→1, type_signals: 4→6; 실행 검사 차이 없음 (not_run)
- confirm_dialog#separated-direct-explicit#r2 none vs ai_improved: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 2→6; 실행 검사 차이 없음 (not_run)
- text_preview#separated-direct-explicit#r0 none vs rule_based: 검사 통과 변화 code_structure: False→True, type_detail: False→True; 신호 files: 1→2, type_signals: 4→5; 실행 검사 차이 없음 (not_run)
- text_preview#separated-direct-explicit#r0 rule_based vs ai_improved: 검사 통과 변화 code_structure: True→False; 신호 files: 2→1; 실행 검사 차이 없음 (not_run)
- text_preview#separated-direct-explicit#r0 none vs ai_improved: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 4→5; 실행 검사 차이 없음 (not_run)
- text_preview#separated-direct-explicit#r1 none vs rule_based: 검사 통과 변화 code_structure: False→True, type_detail: False→True; 신호 files: 1→2, type_signals: 4→5; 실행 검사 차이 없음 (not_run)
- text_preview#separated-direct-explicit#r1 rule_based vs ai_improved: 검사 통과 변화 code_structure: True→False; 신호 files: 2→1; 실행 검사 차이 없음 (not_run)
- text_preview#separated-direct-explicit#r1 none vs ai_improved: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 4→5; 실행 검사 차이 없음 (not_run)
- text_preview#separated-direct-explicit#r2 none vs rule_based: 검사 통과 변화 code_structure: False→True, type_detail: False→True; 신호 files: 1→2, type_signals: 4→5; 실행 검사 차이 없음 (not_run)
- text_preview#separated-direct-explicit#r2 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (not_run)
- text_preview#separated-direct-explicit#r2 none vs ai_improved: 검사 통과 변화 code_structure: False→True, type_detail: False→True; 신호 files: 1→2, type_signals: 4→5; 실행 검사 차이 없음 (not_run)
- password_visibility#separated-direct-explicit#r0 none vs rule_based: 검사 통과 변화 code_structure: False→True; 신호 files: 1→2, type_signals: 5→6; 실행 검사 차이 없음 (not_run)
- password_visibility#separated-direct-explicit#r0 rule_based vs ai_improved: 검사 통과 변화 code_structure: True→False, type_detail: True→False; 신호 files: 2→1, type_signals: 6→4; 실행 검사 차이 없음 (not_run)
- password_visibility#separated-direct-explicit#r0 none vs ai_improved: 검사 통과 변화 type_detail: True→False; 신호 type_signals: 5→4; 실행 검사 차이 없음 (not_run)
- password_visibility#separated-direct-explicit#r1 none vs rule_based: 검사 통과 변화 type_detail: True→False; 신호 type_signals: 5→4; 실행 검사 차이 없음 (not_run)
- password_visibility#separated-direct-explicit#r1 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 수 차이 없음; 실행 검사 차이 없음 (not_run)
- password_visibility#separated-direct-explicit#r1 none vs ai_improved: 검사 통과 변화 type_detail: True→False; 신호 type_signals: 5→4; 실행 검사 차이 없음 (not_run)
- password_visibility#separated-direct-explicit#r2 none vs rule_based: 검사 통과 변화 type_detail: True→False; 신호 type_signals: 6→4; 실행 검사 차이 없음 (not_run)
- password_visibility#separated-direct-explicit#r2 rule_based vs ai_improved: 검사 통과 변화 code_structure: True→False, type_detail: False→True; 신호 files: 2→1, type_signals: 4→5; 실행 검사 차이 없음 (not_run)
- password_visibility#separated-direct-explicit#r2 none vs ai_improved: 검사 통과 변화 code_structure: True→False; 신호 files: 2→1, type_signals: 6→5; 실행 검사 차이 없음 (not_run)
- faq_toggle#separated-direct-explicit#r0 none vs rule_based: 검사 통과 변화 code_structure: False→True; 신호 files: 1→2, type_signals: 2→3; 실행 검사 차이 없음 (not_run)
- faq_toggle#separated-direct-explicit#r0 rule_based vs ai_improved: 검사 통과 변화 code_structure: True→False; 신호 files: 2→1; 실행 검사 차이 없음 (not_run)
- faq_toggle#separated-direct-explicit#r0 none vs ai_improved: 검사 통과 차이 없음; 신호 type_signals: 2→3; 실행 검사 차이 없음 (not_run)
- faq_toggle#separated-direct-explicit#r1 none vs rule_based: 검사 통과 변화 code_structure: False→True; 신호 files: 1→2, type_signals: 2→3; 실행 검사 차이 없음 (not_run)
- faq_toggle#separated-direct-explicit#r1 rule_based vs ai_improved: 검사 통과 변화 type_detail: False→True; 신호 files: 2→3, type_signals: 3→5; 실행 검사 차이 없음 (not_run)
- faq_toggle#separated-direct-explicit#r1 none vs ai_improved: 검사 통과 변화 code_structure: False→True, type_detail: False→True; 신호 files: 1→3, type_signals: 2→5; 실행 검사 차이 없음 (not_run)
- faq_toggle#separated-direct-explicit#r2 none vs rule_based: 검사 통과 변화 code_structure: False→True; 신호 files: 1→2, type_signals: 2→3; 실행 검사 차이 없음 (not_run)
- faq_toggle#separated-direct-explicit#r2 rule_based vs ai_improved: 검사 통과 변화 code_structure: True→False; 신호 files: 2→1; 실행 검사 차이 없음 (not_run)
- faq_toggle#separated-direct-explicit#r2 none vs ai_improved: 검사 통과 차이 없음; 신호 type_signals: 2→3; 실행 검사 차이 없음 (not_run)
- cart_quantity#separated-direct-explicit#r0 none vs rule_based: 검사 통과 변화 code_structure: False→True, type_detail: False→True; 신호 files: 1→3, type_signals: 3→5; 실행 검사 차이 없음 (not_run)
- cart_quantity#separated-direct-explicit#r0 rule_based vs ai_improved: 검사 통과 변화 code_structure: True→False; 신호 files: 3→1; 실행 검사 차이 없음 (not_run)
- cart_quantity#separated-direct-explicit#r0 none vs ai_improved: 검사 통과 변화 type_detail: False→True; 신호 type_signals: 3→5; 실행 검사 차이 없음 (not_run)
- cart_quantity#separated-direct-explicit#r1 none vs rule_based: 검사 통과 변화 code_structure: False→True, type_detail: True→False; 신호 files: 1→2, type_signals: 5→3; 실행 검사 차이 없음 (not_run)
- cart_quantity#separated-direct-explicit#r1 rule_based vs ai_improved: 검사 통과 변화 type_detail: False→True; 신호 files: 2→3, type_signals: 3→5; 실행 검사 차이 없음 (not_run)
- cart_quantity#separated-direct-explicit#r1 none vs ai_improved: 검사 통과 변화 code_structure: False→True; 신호 files: 1→3; 실행 검사 차이 없음 (not_run)
- cart_quantity#separated-direct-explicit#r2 none vs rule_based: 검사 통과 변화 code_structure: False→True, type_detail: False→True; 신호 files: 1→2, type_signals: 3→9; 실행 검사 차이 없음 (not_run)
- cart_quantity#separated-direct-explicit#r2 rule_based vs ai_improved: 검사 통과 차이 없음; 신호 files: 2→4, type_signals: 9→8; 실행 검사 차이 없음 (not_run)
- cart_quantity#separated-direct-explicit#r2 none vs ai_improved: 검사 통과 변화 code_structure: False→True, type_detail: False→True; 신호 files: 1→4, type_signals: 3→8; 실행 검사 차이 없음 (not_run)
