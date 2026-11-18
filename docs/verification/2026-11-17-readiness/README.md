# 차주 운영·시연 계획 선행 실행 — 2026-11-17

주간보고서 v0.10의 **11/20~11/26 계획을 11/17에 미리 실행한 기록**이다. 발표일이나 기존 실적 기간을 변경하지 않는다. 실제 사용자 자료·유료 모델 API를 사용하지 않았다. 기존 v0.10 PDF와 고정 실험 응답은 보존한다.

## CI에서 건너뛴 세 검사

| 검사 | CI에서 제외된 이유 | 기존 최신 로컬 기록 | 이번 확인 |
|---|---|---|---|
| `test_recompute_matches_saved` | 저장소에 MACSum 원본 데이터가 없음 | 11/17 전체 JUnit에 통과 | 현재 코드에서 다시 통과 |
| `test_personas_come_from_real_macsum_attributes` | 같은 MACSum 데이터가 없음 | 같은 JUnit에 통과 | 현재 코드에서 다시 통과 |
| `test_full_cached_audit_is_offline_and_preserves_unknown_outcomes` | RACE·EvalPlus 고정 공개 파일 캐시가 없음 | 같은 JUnit에 통과 | 현재 캐시로 다시 통과 |

`tests/conftest.py`의 `macsum` 조건과 `tests/test_coding_public.py`의 캐시 조건을 대조했다. 이전 검사 증거는 [11/17 전체 검사](../2026-11-17/results/full.xml), 재검사 증거는 [로그](results/skipped-recheck.log)와 [JUnit](results/skipped-recheck.xml)이다. 이 세 개와 로컬 Windows의 심볼릭 링크 권한 때문에 건너뛴 한 개는 서로 다른 검사다. 실제 모델 API 16개는 요청대로 계속 제외한다.

CI 명령에 `-rs`를 추가하여 앞으로는 건너뛴 이유가 로그에 표시된다. 데이터 다운로드나 모델 호출을 CI에 추가하지 않았다.

## 계획별 결과

| v0.10 차주 계획 | 수행한 작업 | 근거·완료 경계 |
|---|---|---|
| 실행 환경·시연 준비 | 무료 데모 실행 절차, 합성 원문·계정 준비, 실제 빌드 화면 확인 | [시연 안내](DEMO.md), [브라우저 결과](results/browser.json). 깨끗한 Linux 컨테이너 설치는 동일 게시 커밋의 Hosted container 실행으로 별도 확인한다. |
| 복구·접근 경계 점검 | SQLite 온라인 백업, 무결성·해시 검사, 새 저장소 복원, 재시작, 다른 계정 차단 | [서버 10항목](results/storage.json), [백업 검사 7개](results/snapshot.xml). 실제 사용자 DB는 사용하지 않았다. |
| 시연·잔여 오류 수정 | 조건 충돌 확인 지침의 직접 저장 연결, 저장 후 새 원문 재사용, 코딩 두 기능·로그아웃·모바일 확인 | [화면 6항목](results/browser.json), [요약 저장 화면](results/02-summary-saved.png). 사람의 사용성 평가가 아니다. |
| 문서·공유 자료 정리 | 실행·복구 안내, 설계 원고·UC/WBS 연결, 제출물 목록, GitHub 변경/자동 검사 | [최종 인계 체크리스트](HANDOFF.md). 기존 PDF는 발행 당시 판본으로 유지한다. |

## 수정한 동작

요약의 `이번 원문의 조건 충돌 확인`은 확인 결과를 복사할 수 있었지만 보관함에 바로 저장할 수 없었다. 아래쪽 저장 폼은 예시 비교의 기본 지침을 대상으로 했으므로 사용자가 방금 바꾼 조건을 저장한다고 오해할 수 있었다.

이제 충돌을 해소한 **현재 언어의 재사용 지침** 옆에서 명시적으로 저장하고 보관함으로 이동한다. 원문·선택 문장·새 작업은 저장하지 않는다. 조건·원문 변경 시 이전 결과와 저장 폼을 숨긴다. 기본 비교 지침은 별도라는 안내와 두 폼의 고유 입력 ID를 추가했다. 새 API·DB migration·의존성은 없다. 새 원문의 보존 문장·분량 충돌은 다시 확인해야 한다.

`scripts/storage_snapshot.py`는 Python 표준 라이브러리로 SQLite `backup()`을 사용해 실행 중의 커밋된 WAL 내용과 첨부 BLOB을 보존한다. 캐시 폴더는 명시한 경우만 포함한다. SHA-256·파일 목록·SQLite quick_check·테이블 행 수를 확인하며 기존 폴더에는 복원하지 않는다. 손상·누락·추가 파일·경로 변조·덮어쓰기 거절을 검사했다. 초기 Windows 검사에서 SQLite 연결이 닫히지 않아 파일 잠금이 남는 문제를 발견하여 연결 종료를 명시하고 7개 검사를 재실행했다.

## 검증 재현

최신 로컬 결과는 Python **1,440 통과·1 건너뜀·API 16개 제외**, 프론트 **137 통과**, 프로덕션 빌드 성공이다. 심볼릭 링크 한 건은 Windows 권한 제한이며 CI Linux 결과와 구분한다. 새 백업 도구 7개 검사는 전체 Python 수치에 포함된다. 실제 HTTP 운영 리허설 10항목과 Chromium 화면 6항목은 별도다. 빌드의 기존 큰 번들 경고는 남아 있다.

Python 3.12와 저장소의 기존 의존성을 사용한다. `.env` 로딩과 모델 키를 제거하고 live 플래그를 모두 끈다. 아래 래퍼는 Python 외부 소켓을 차단하며 테스트의 로컬 HTTP만 허용한다. 시스템 수준의 모든 프로세스 네트워크 격리라고 주장하지 않는다.

```powershell
.venv/Scripts/python.exe -X utf8 docs/verification/2026-11-17-readiness/offline.py pytest tests/test_checks_vs_labels.py::test_recompute_matches_saved tests/test_persona.py::test_personas_come_from_real_macsum_attributes tests/test_coding_public.py::test_full_cached_audit_is_offline_and_preserves_unknown_outcomes -vv -rs
.venv/Scripts/python.exe -X utf8 docs/verification/2026-11-17-readiness/offline.py pytest tests/test_storage_snapshot.py -q
.venv/Scripts/python.exe -X utf8 docs/verification/2026-11-17-readiness/rehearse_storage.py
node --test "frontend/src/**/*.test.js"
npm run build --prefix frontend
```

브라우저 재현은 [DEMO.md](DEMO.md)의 별도 저장소 서버를 켠 뒤 `node docs/verification/2026-11-17-readiness/browser.cjs`로 한다. 기존 설치된 Playwright/Chromium 경로는 해당 스크립트의 환경변수로 바꿀 수 있다. 새 패키지는 추가하지 않았다. 첫 시연 스크립트의 Windows 클립보드 CRLF 차이와 빠진 코딩 확인 단계를 수정했으며 실패한 진단 실행은 성공에 포함하지 않았다.

전체 수치·소스 및 결과 파일 해시는 [validation.json](results/validation.json)에 수집한다. [전체 Python 로그](results/full.log), [프론트 로그](results/frontend.log), [빌드 로그](results/build.log)를 함께 보관한다. 실제 사용자 선호·시간 절감·팀 채택, 공개 배포, 유료 실제 모델 검증, 팀원 참석 시연은 이 결과에 포함하지 않는다.
