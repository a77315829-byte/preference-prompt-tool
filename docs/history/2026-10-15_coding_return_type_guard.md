# 코딩 AI 반환 타입 검사 보강 — 2026-10-15

## 변경 사항

- `checks/coding.py`: 타입 명시 선호일 때 공개 함수의 반환 타입 누락을 검사한다.
- 타입 표기의 총개수가 충분해도 공개 함수 경계의 누락은 별도로 거부한다.
- 기존 생성 흐름의 같은 모델 수정 요청 및 수정 실패 시 거부 경로를 재사용한다.
- 저장된 실제 AI 응답은 수정하지 않았다.

## 검증 결과

- 관련 테스트 69개 통과, `git diff --check` 통과.
- 저장된 FAQ 응답 2개를 재검사해 기존에 발견한 공개 함수 반환 타입 누락 1건을 검출했다.
- 회귀 테스트 3개 추가: 타입 신호가 많아도 누락 검출, 수정 후 A/B 표시 허용,
  수정 후에도 누락이 남으면 거부.
- API 호출은 모의 응답으로 대체했다. 추가 유료 호출은 0회다.

```bash
.venv/bin/python -m pytest tests/test_coding_domain.py tests/test_coding_persona_evaluation.py tests/test_coding_ai_quality_stage4.py tests/test_coding_ai_quality_benchmark.py -q -m 'not api'
```

## 한계와 다음 단계

이번 검사는 단순한 named export 함수 선언을 대상으로 하는 보조 규칙이다.
화살표 함수, 중첩 함수 매개변수 등 모든 TypeScript 구문을 분석하지 않는다.
실제 AI가 수정 요청을 받아 올바른 코드를 생성하는지는 이번에 재검증하지 않았다.
저장된 FAQ의 전체 품질 판정은 여전히 미통과이며, 실제 수정 응답에 대한
타입·빌드·동작·독립 스타일 검증과 추가 호출 비용 기록이 남아 있다.

브랜치: `codex/coding-ai-upgrade`. 커밋·푸시는 진행하지 않았다.
