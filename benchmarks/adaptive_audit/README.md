# 짧은 선택 흐름의 독립 검사

2026-11-09, 기준 `4078021`. 두 Codex 보조 에이전트가 각각 화면/종료와 저장/호환을 검사했다.
모델 API 호출·새 의존성 설치 없이 실제 React 상태 흐름, Python 검증기와 SQLite를 사용했다.

- `flow-audit.mjs`: 실제 App을 JSDOM에 렌더링하고 HTTP를 모의 응답으로 대체한다. 1~8회 각각의 완료, 보류/엇갈림/일치 구분, 메뉴 복원, 앞선 선택 변경, 취소를 검사한다.
- `fixture.py`: 실제 예시 은행을 만들거나 `validate` 인자로 UI가 만든 10개 프로필을 실제 백엔드에 대조한다.
- `summary-audit.py`: 영어·한국어 데모 요약의 A/B/동률 경로를 순회한다. 완료 450경로, 마지막 선택 취소/교체 1,350경로, 그중 추가 질문 재개 96경로를 확인했다. 사용자 450명이나 실제 모델 450회 실험이 아니다.
- `test_storage_audit.py`: v1/v2/v3 및 v4의 1~8회 기록에 대해 직접 수정·DB 재개·재사용·내보내기와 개선 메타데이터 저장을 검사한다. 실제 GEPA 최적화는 실행하지 않는다.
- `examples.json`, `profiles.json`, `report.txt`: 출처 ID 보완 전 독립 화면 검사의 원자료다. 수정 후에도 이 10개 과거 프로필이 정상 검증되는 것을 부모 에이전트가 확인했다.

저장 검사 최초 결과는 21통과/2실패였다. 언어를 바꾼 v4 기록이 수용되는 결함과 v3의 null 출처 처리 오류를 부모가 재현하고 수정했다. 이후 관련 122개 검사가 통과했다. [수정과 한계](../../docs/history/2026-11-09_adaptive_validation.md).

## 다시 실행

커밋된 원자료를 덮어쓰지 않도록 파일을 `tmp/<새 감사 ID>/`에 복사한 뒤 해당 경로에서 실행한다. 저장소 루트에서 두 단계 아래여야 상대 경로가 맞는다. 기존 설치 패키지를 사용한다.

```powershell
.venv/Scripts/python.exe -B tmp/<새 감사 ID>/fixture.py
node tmp/<새 감사 ID>/flow-audit.mjs
.venv/Scripts/python.exe -B tmp/<새 감사 ID>/fixture.py validate
.venv/Scripts/python.exe -B tmp/<새 감사 ID>/summary-audit.py
.venv/Scripts/python.exe -B -m pytest benchmarks/adaptive_audit/test_storage_audit.py --basetemp=tmp/<새 pytest ID> -q
```

요약은 API 없는 데모 후보를 사용한다. 브라우저 시각/접근성, 배포 서버, 실제 AI 응답, 사람의 선호 추정 정확도는 검사 범위에 포함되지 않는다.
