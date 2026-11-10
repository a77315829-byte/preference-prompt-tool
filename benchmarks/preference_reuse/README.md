# 선호 설정·저장·재사용 계약 감사

2026-11-10. [현재 제품 목표](../../docs/coding-preference-usability-plan.md)에 맞춰 독립 보조 에이전트가 검사했다. 유료 모델 API 호출은 없었다. 실제 사람의 편의성·시간 절약·선호 추정 정확도를 측정한 실험은 아니다.

## 결과

Python/FastAPI, JavaScript/React, TypeScript/React, Python/Flask, Java/Spring Boot의 **5개 환경 × 16개 선호 조합 × 직접 설정/4회/8회 비교 = 240개 경로**를 확인했다. 같은 최종 선택이 같은 선호 규칙으로 조립됐고, 작업 요청을 바꿔 복사하거나 한 항목을 바꿔 새로 저장해도 원본이 유지됐다.

| 검사 그룹 | 통과 | 실패 |
|---|---:|---:|
| 경로별 선택·규칙 일치 | 240 | 0 |
| 저장·DB 재개·작업 내용 분리 | 240 | 0 |
| 한 항목 변경·별도 새 저장 | 960 | 0 |
| 5종 내보내기·원본 보존 | 1,200 | 0 |
| 같은 환경의 예시 출처 안정성 | 160 | 0 |
| 다른 환경의 비교 출처 거절 | 20 | 0 |

합계 2,820은 같은 조합을 여러 그룹에서 검사한 **계약 사례 수**다. 독립 사용자나 코드 과제 2,820개가 아니다. React와 Flask의 준비 예시는 언어 기본 예시이고, FastAPI와 Spring Boot는 프레임워크 전용 예시다. 출처 구분을 그대로 검사했다.

실제 React App/JSDOM과 Python 조립·저장 함수를 연결한 흐름은 **3/3 통과**했다: FastAPI 4회, JavaScript/React 직접 설정, TypeScript/React 8회. 지침 생성 → 작업 A/B 교체 복사 → 지침만 저장 → 보관함 재사용 → 주석만 변경 → 별도 저장을 확인했다. 통신은 모의 fetch와 자식 Python 프로세스의 stdin/stdout이며 DB는 격리된 실제 SQLite다. 인증과 클립보드는 모의 구현이다. 실제 HTTP 라우팅·로그인·OS 클립보드·브라우저 배치 검사는 포함하지 않는다.

확인한 범위에서 제품 결함은 발견하지 않았다. 기존 코드 결과 비교나 이번 검사만으로 사람이 더 편하게 쓰거나 코드가 더 정확해진다고 주장하지 않는다. 실제 브라우저에서 친구 브랜치의 파스텔 UI를 확인한 기록은 [별도 보고서](../../docs/history/2026-11-10_goal_and_ui_check.md)에 있다.

## 보존 자료

- [백엔드 원자료](results/2026-11-10/contracts.json): 그룹별 결과·실패 목록·검사 대상 SHA-256.
- [실제 조립된 대표 프롬프트](results/2026-11-10/sample-prompts.json).
- [최종 UI 원자료](results/2026-11-10/ui-results.json): 3개 시나리오·체크포인트·파일 해시·Python 실행 경로.
- [최초 UI 원자료](results/2026-11-10/ui-results-system-python.json): 같은 3개 시나리오의 최초 실행. 재실행과 합쳐 6개 독립 사례로 세지 않는다.
- [검토자의 보고서](results/2026-11-10/REPORT.txt): 실행 당시 임시 경로와 범위 기록.

검사 시작 HEAD는 `def4d7cf3bb32d40770e70e91205a6ee7a708eb2`다. 백엔드는 해당 버전과 같고 UI에는 이번 안내 문구 수정이 포함됐다. 결과에 기록된 검사 전후 소스 해시는 동일하다.

백엔드와 최초 UI 실행은 시스템 Python 3.12.10을 사용했다. UI 스크립트의 인터프리터 선택을 프로젝트 `.venv`로 고정한 뒤 같은 세 시나리오를 다시 실행했고 통과했다. 최종 UI 원자료에 `.venv/Scripts/python.exe`, Python 3.12.10이 기록돼 있다. 백엔드 원자료를 `.venv`에서 실행한 결과로 바꾸어 표현하지 않는다.

## 재현

저장소의 기존 Python 3.12 가상환경과 설치된 프론트 의존성이 필요하다. 새 패키지·API 키·서버·사용자 DB는 필요하지 않다. 아래 명령은 저장소 루트의 PowerShell에서 실행한다. 스크립트가 저장소 루트를 두 단계 위에서 찾으므로 `tmp` 바로 아래의 전용 폴더에 복사한다.

```powershell
$auditFolder = Join-Path 'tmp' ('preference-reuse-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $auditFolder
Copy-Item -LiteralPath 'benchmarks/preference_reuse/audit_contracts.py' -Destination $auditFolder
Copy-Item -LiteralPath 'benchmarks/preference_reuse/backend_bridge.py' -Destination $auditFolder
Copy-Item -LiteralPath 'benchmarks/preference_reuse/audit_ui.mjs' -Destination $auditFolder
& .\.venv\Scripts\python.exe -X utf8 -B (Join-Path $auditFolder 'audit_contracts.py')
node (Join-Path $auditFolder 'audit_ui.mjs')
```

각 실행은 그 폴더 아래 새 결과 폴더와 임시 DB를 만든다. 보존한 결과 파일과 실제 사용자 DB를 덮어쓰지 않는다. 이 자료에는 감사용 DB를 포함하지 않았다.
