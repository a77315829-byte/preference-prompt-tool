# 두 계정 공유·첨부·권한과 최신 회귀 검사

사용자 요청에 따라 2026-11-12 로컬 `microstone` 작업 상태를 검증했다. 실제 사용자 계정·DB를 사용하지 않고 `tmp/integration-20261112/`의 테스트 SQLite와 합성 계정을 사용했다. 결과 집계는 완료한 실행에서 `collect_results.py`가 생성하는 [results.json](results.json)을 기준으로 한다.

## 검증 방법

- 기존 설치된 Chromium/Playwright, 실제 프로덕션 빌드, `hosting_server.py`의 HTTP 처리와 SQLite를 연결했다. 별도 라이브러리를 설치하지 않았다.
- 두 활성 계정은 쿠키가 분리된 브라우저 컨텍스트를 사용했다. 수신자 교체용 계정 하나와 익명 컨텍스트를 대조로 추가했다.
- 계정 생성, 작업 작성, 파일 선택·첨부·제외·공유, 다운로드·새 탭 미리 보기, 재열기, 충돌, 이어받기, 완료·재개, 기록 보기, 로그아웃·재로그인은 실제 화면에서 실행했다.
- 위조 편집·공유 전 기록·익명/제3자 파일 접근, 팀 지침 생성·초대·가입·조합·원본 보존·오래된 팀 버전 충돌은 동일 브라우저 쿠키를 쓰는 실제 HTTP 요청으로 별도 확인했다. 이 부분을 모두 UI 클릭 검사로 표현하지 않는다.
- 이어받기 **전** 수신자를 변경했을 때 이전 수신자의 본문·기록·첨부 접근이 거절되는지 확인했다. 이미 다운로드한 파일이나 클립보드의 복사본을 회수하는 기능은 아니다.

## 발견한 문제와 수정

### 거절 후 남는 인수인계 화면

수신자를 다른 계정으로 바꾸면 서버는 기존 수신자의 본문·기록·첨부 요청을 404로 거절했다. 하지만 이미 열린 화면의 ‘작업 열기’가 거절될 때 오류만 표시하고 이전 본문·임시 초안을 유지했다. `browser-run2`에서 실제 화면으로 재현했다.

`handoffApi.js`가 HTTP 오류 상태를 보존하도록 하고, `HandoffsSection.jsx`에서 현재 읽기 권한이 없음을 확인하면 해당 작업의 화면·목록·기록·임시 초안을 정리하도록 수정했다. 단순한 기록 부재·편집 거절은 현재 자료를 다시 조회해 접근 여부를 구별한다. 버전 충돌 409와 일시 장애는 미저장 초안을 버리지 않는다. 자동으로 다른 계정의 화면을 실시간 삭제하는 기능을 추가한 것은 아니다.

관련 UI 회귀 3개를 추가했다. 재열기·이전 기록 조회 후 회수 처리와, 현재 읽기 권한이 유효한 기록 404/서버 장애의 초안 보존을 확인한다. 기존 버전 충돌·파일 실패 재시도 검사도 유지한다. 관련 묶음은 10개 통과했고 수정 빌드의 전체 18시나리오를 다시 실행했다.

### 요약 보조 설정을 엔진 도메인으로 수집

전체 검사에서 `summary_contract.yaml`을 엔진 도메인으로 읽는 네 검사가 실패했다. 해당 파일은 축·검사 모듈을 정의하는 도메인이 아니라 영어·한국어 조건 처리 지침 자료다. 제품의 별도 조건 처리 함수에서 읽으며 엔진 도메인 로더로 읽지 않는다.

`tests/domain_inventory.py`에 이 보조 자료 하나를 명시하고, 다른 모든 최상위 YAML은 기존 엔진 검사를 계속 받도록 했다. 필드가 없거나 로드에 실패한 파일을 동적으로 건너뛰는 방식이 아니다. 보조 자료는 `test_summary_contracts.py`의 영어·한국어 형식 검사 두 개로 확인한다. 따라서 잘못 수집한 네 건이 전용 두 건으로 바뀌어 전체 검사 수가 달라진다. 원래 YAML 경로·내용과 고정 실험의 해시는 보존했다. 관련 122개 검사가 통과했다.

## 환경 문제와 검증 범위

최초 제한된 실행 환경에서는 로컬 HTTP 연결이 실패했고 Chromium 실행도 거절됐다. 그 실행은 중단해 제품 실패 집계와 구분했다. 로컬 서버/브라우저 접근이 가능한 환경으로 옮긴 뒤 HTTP 검사 29개를 통과하고 전체 검사를 다시 실행했다. 첫 브라우저 시도의 파일 링크 접근성 이름 공백 차이는 검증 선택자를 실제 요소에 맞춰 고쳤으며 제품 결함으로 세지 않았다.

`offline_python.py`는 `.env` 로딩을 끄고 모델 키와 LIVE 설정을 제거하며 테스트 DB를 사용한다. Python 프로세스는 루프백 외 연결을 차단하고 실제 API 검사에는 `not api` 조건을 적용했다. 브라우저도 외부 주소 요청을 차단했다. 유료 모델 API는 호출하지 않았다. 테스트 로그의 `api` 경로는 로컬 웹 앱 API이며 모델 API 과금과 다르다.

남는 한계는 Windows 심볼릭 링크 생성 권한으로 건너뛴 검사, 실제 모델 API 제외, 기존 번들 크기 경고다. 합성 계정의 기술 검증이며 사람의 사용 편의성·만족도·시간 절감이나 공개 배포, 전체 보안 검증은 아니다. 비교 메모리 세션의 계정 소유권 정책도 이번 인수인계 검증과 다른 범위다.

## 재실행과 근거

기존 Python 3.12 가상환경·프론트 의존성이 필요하다. `offline_python.py`의 서버는 127.0.0.1:18762를 사용하며 기존 사용자 서버와 다른 주소다. 이 실행용 브라우저 경로는 Windows의 설치 위치이므로 다른 환경에서는 기존 설치 경로로 조정한다. 재검사 시 결과 디렉터리를 새로 지정하고 완료 기록을 덮어쓰지 않는다.

```powershell
.venv/Scripts/python.exe -X utf8 docs/verification/2026-11-12/offline_python.py pytest -q
node --test 'frontend/src/**/*.test.js'
npm.cmd run build --prefix frontend
# 테스트 서버를 별도 실행한 상태에서:
node docs/verification/2026-11-12/browser_integration.cjs browser-new-run
```

- [검사 집계](results.json)
- [전체 백엔드 최종 로그](results/backend-final.log), [수정 전 실패 로그](results/backend-before-fix.log)
- [프론트 전체 로그](results/frontend-final.log), [빌드 로그](results/build.log)
- [18시나리오 결과](results/browser.json), [수정 전 UI 재현](results/browser-before-fix.json)
- [최종 코드 342개 해시](results/source-hashes.json), [외부 연결 차단 기록](results/offline-guard.json)

보고서에 포함할 근거만 복사했으며 계정 비밀번호·쿠키·DB는 포함하지 않는다. 위 로컬 검증 실행 당시에는 원격 push·공개 배포를 하지 않았으며, 이후 사용자 요청에 따라 코드와 보고서를 GitHub에 게시했다. 아래는 그 후속 CI 확인 기록이다.

## GitHub CI 완료와 건너뛴 3개 재검증

검증 커밋은 `c7848083c4c0931fb7c3f649e3f4087685e31a11`이다. 2026-11-12 [브랜치 Tests](https://github.com/a77315829-byte/preference-prompt-tool/actions/runs/43210641135), [PR Tests](https://github.com/a77315829-byte/preference-prompt-tool/actions/runs/43210647977), [Hosted container](https://github.com/a77315829-byte/preference-prompt-tool/actions/runs/43210641521)가 모두 성공했다. 두 Tests 실행 각각 Python 1,353 통과·3 건너뜀·API 16개 제외, 프론트 123 통과다. 컨테이너 빌드·실행·JS/TS 도구·재시작 후 데이터 유지를 확인했으며 공개 서비스 배포를 뜻하지 않는다.

| CI에서 건너뛴 검사 | 이유 | 이전 로컬 전체 / 별도 재검증 |
|---|---|---|
| `test_checks_vs_labels.py::test_recompute_matches_saved` | MACSum 원문 없음 | 통과 / 통과 |
| `test_persona.py::test_personas_come_from_real_macsum_attributes` | MACSum 원문·속성 없음 | 통과 / 통과 |
| `test_coding_public.py::test_full_cached_audit_is_offline_and_preserves_unknown_outcomes` | 고정 버전 RACE/EvalPlus 자료 캐시 없음 | 통과 / 통과 |

`data/`는 저장소에서 제외하며 CI가 해당 자료를 자동 내려받지 않는다. 같은 코드의 수집 목록과 로컬·CI 진행 로그 각각의 1,356개 결과 순서를 대조해 위 세 항목을 확인했다. 세 검사만 별도로 다시 실행해 **3 통과·0 실패·0 건너뜀, 6.55초**를 확인했다. `.env` 로딩·모델 키·LIVE 설정을 끄고 소켓 연결을 차단했으며 외부 연결 시도·유료 모델 API 호출은 0회다. 검증된 소스 342개의 해시도 그대로다.

로컬의 Windows 권한 제한으로 빠졌던 `test_symlink_outside_build_is_not_served`는 CI에서 통과했다. 따라서 로컬 1,355 통과·1 건너뜀과 CI 1,353 통과·3 건너뜀의 차이를 제품 실패로 해석하지 않는다. 재검증 3개는 기존 로컬 검사에 포함되므로 합산하지 않는다. 실제 API 검사 16개는 실행하지 않았다. RACE/EvalPlus 검사는 자료 무결성과 준비 경로 확인이며 새 모델 출력의 실행 정확도 검사가 아니다.

- [집계·검증 범위](ci/results.json), [원격 실행 상태·단계](ci/runs.json)
- [브랜치 검사 발췌](ci/push-test-excerpt.log), [PR 검사 발췌](ci/pr-test-excerpt.log)
- [검사 이름 대조](ci/comparison.json), [같은 코드의 수집 목록](ci/collected.json)
- [개별 재검증 로그](ci/focused.log), [JUnit XML](ci/focused.xml), [네트워크 차단 기록](ci/focused-guard.json)

원자료는 기존 완료 실행을 보존한 것이다. 보고서 게시 커밋이 만드는 새로운 CI 실행은 별도이며 그 결과를 위 실행에 소급해 넣지 않는다.
