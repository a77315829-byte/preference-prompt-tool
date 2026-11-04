# 2단계 전체 회귀 테스트·빌드 — 2026-10-15

## 범위

- 브랜치: `codex/coding-ai-upgrade`
- Python: 로컬 `.venv`의 Python 3.12.14
- 기존 변경 사항을 보존한 상태에서 현재 작업 트리를 검사했다.
- 유료 AI 호출은 하지 않았다. 커밋·푸시는 하지 않았다.

## 결과

| 검사 | 결과 |
| --- | --- |
| `.venv/bin/python -m pytest -m 'not api' -q --tb=short` | 850 통과, 2 건너뜀, 16 제외, 실패 0 (99.13초) |
| `node --test 'frontend/src/**/*.test.js'` | 9 통과, 실패 0 |
| `npm run build --prefix frontend` | 통과, Vite 7.3.6, 459 modules |
| `git diff --check` | 통과 |

프론트 테스트 9개는 현재 저장소에 있는 복사 상태 함수 테스트다. 모든 화면을 자동 조작하는 브라우저 테스트 9개라는 뜻은 아니다.

## 건너뛴 항목

아래 두 테스트는 `data/macsum/dataset/macdoc/val.json` 데이터가 없어 건너뛰었다. 해당 테스트를 `-rs`로 별도 실행해 이유를 확인했다.

- `tests/test_checks_vs_labels.py`: MACSum 사람 라벨과 검사 결과의 비교
- `tests/test_persona.py::test_personas_come_from_real_macsum_attributes`: 실제 MACSum 속성을 이용한 페르소나 검사

`api` 표시가 있는 16개는 비용 발생 가능성이 있어 의도적으로 제외했다. 실제 모델 생성 품질·호출 성공·청구 금액을 이번 회귀 테스트로 검증했다고 해석하지 않는다.

## 실행 환경 문제 구분

첫 제한 환경 실행에서는 로컬 HTTP 서버의 `socket.bind`가 `PermissionError: [Errno 1] Operation not permitted`로 막혔다. 당시 결과는 789 통과, 10 실패, 51 오류, 2 건너뜀, 16 제외였다.

로컬 테스트 서버 실행 권한을 허용한 동일 범위 재실행에서는 850개가 모두 통과했다. 첫 실행의 실패·오류는 재현된 코드 회귀가 아니라 실행 환경 제한으로 분류한다. 테스트 통과를 위해 애플리케이션 코드나 테스트 기대값을 바꾸지 않았다.

## 다음 단계

- 기존 AI 실행 기록의 사용량·비용 정리
- 실제 청구 확인 여부와 토큰 기준 계산 금액 구분
- 발표 자료·시연 준비
- 브라우저 검수의 미확인 항목은 `2026-10-15_ui_final_qa.md` 참고
