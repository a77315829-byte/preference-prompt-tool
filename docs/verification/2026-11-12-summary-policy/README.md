# 요약 길이·조건 충돌 v2 기술 검증

[변경 범위·정책·한계](../../history/2026-11-12_summary_length_policy.md).
실제 사용자 자료 대신 합성 원문, 별도 DB, 독립 브라우저 저장소를 사용한다.

## 실행 방법

저장소 루트의 Python 3.12 가상환경과 설치된 프런트엔드 의존성을 사용한다. 새 라이브러리는 설치하지 않았다.

```powershell
.venv/Scripts/python.exe docs/verification/2026-11-12-summary-policy/offline_python.py pytest tests/test_summary_policy_v2.py tests/test_summary_contracts.py -q --junitxml=tmp/summary-policy-20261112/focused.xml
.venv/Scripts/python.exe docs/verification/2026-11-12-summary-policy/offline_python.py pytest -q --junitxml=tmp/summary-policy-20261112/full.xml *> tmp/summary-policy-20261112/full.log
node --test "frontend/src/**/*.test.js" *> tmp/summary-policy-20261112/frontend.log
npm.cmd run build --prefix frontend *> tmp/summary-policy-20261112/build.log
.venv/Scripts/python.exe docs/verification/2026-11-12-summary-policy/offline_python.py server
```

서버를 실행한 채 별도 터미널에서 `node docs/verification/2026-11-12-summary-policy/browser.cjs`를 실행한다.
브라우저 스크립트는 설치된 Playwright·Chromium을 사용하며 다른 환경은 `PLAYWRIGHT_MODULE`, `CHROMIUM_PATH`로 위치를 지정한다.
실행 주소는 `127.0.0.1:18763`, DB와 임시 로그는 `tmp/summary-policy-20261112/`다.
Windows 제한 환경에서는 로컬 HTTP·브라우저 실행 권한이 필요할 수 있다.

`offline_python.py`는 dotenv를 비활성화하고 모델 자격 증명·LIVE 설정을 제거하며 Python의 비로컬 TCP 연결을 차단한다.
자식 테스트 프로세스는 제거된 환경을 상속한다. 브라우저도 로컬 서버 외의 요청을 차단한다.
`api` 표시 테스트는 제외한다. 모델 응답 품질의 유료 실행을 대체한 것으로 해석하지 않는다.

실제 기록은 위 명령들의 출력을 `full.log`, `frontend.log`, `build.log`에 저장한 뒤
`collect_results.py`로 결과와 해시를 수집했다. 해당 스크립트는 테스트를 재실행하지 않는다.

## 증거 파일

- [검사 수·시간·건너뜀 이유·소스 해시](results/validation.json)
- [Python 전체 로그](results/full.log), [프런트엔드 전체 로그](results/frontend.log), [빌드 로그](results/build.log)
- [실제 브라우저 8개 시나리오·HTTP 요청 기록](results/browser.json)
- [긴 원문 안내](results/source-limit.png), [문장 부족 충돌](results/short-source-conflict.png), [모바일 선택 화면](results/mobile-conflict.png)

과거 실험을 평가용으로 다시 사용하거나 결과 파일을 수정하지 않았다. v0.6 이전 검사와 이번 검사 증거는 별도 디렉터리에 보관한다.
소스 해시 비교는 이전 검사에 기록된 342개 파일을 기준으로 한다. 변경이 허용된 공통 API·요약 UI·CSS·검사 5개 이외의 차이는 수집 시 오류로 처리한다.
