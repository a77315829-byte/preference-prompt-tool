# 일반 요청·직접 설정·짧은 예시 비교의 코드 결과

2026-11-09, 독립된 Codex 보조 에이전트 3개, 조건당 1회. 별도 모델 API 호출 0회.
기존 실제 React JSX 버그를 다시 사용했으므로 새로운 과제 표본이 늘어난 실험은 아니다.

| 조건 | 고정 기능 검사 | 에이전트 작업 시간 | 프로덕션 변경 줄 |
|---|---:|---:|---:|
| 일반 요청 | 9/9 | 206.731초 | +13 / −3 |
| 직접 설정 | 9/9 | 175.225초 | +14 / −2 |
| 4회 예시 비교 | 9/9 | 180.302초 | +7 / −4 |

수정 전 기준 코드는 5/9였다. 세 안 모두 첫 제출에서 통과했다. 코드 줄 수는 품질 점수가 아니다.
사람의 선호·설정 시간·수정 시간은 미측정이다. 작업 시간은 분석·수정·자체 검사와 도구 대기를 포함한다.
조건별 1회, 같은 호스트에서 겹친 실행이므로 관측 시간 차이를 인과적 우위로 해석하지 않는다.

## 고정한 조건

- 코드: `3b6b550418dcaf8cb184563f699bdc727f5dd54b`의 동일 복사본.
- 지침 생성: `4078021`의 실제 `general_prompt` / `build_coding_instructions`.
- 공통 과제: 부모의 작업 요청 변경을 미편집 비교 양식에 반영하고, 직접 편집·빈 입력·저장 기록을 보호하며 새 비교를 초기화한다.
- 세 에이전트는 부모 대화 이력 없이 동일 모델·추론 설정을 상속했다. 별도 모델 ID는 지정하지 않았다.
- 직접 설정과 예시 비교: JavaScript/React, 핵심 설명·필요한 주석·간결한 구성·변경 부분 중심으로 동일하게 고정.
- 예시 조건은 실제 v4 비교 앞 4개에 응답한 프로필로 생성했다. 네 항목 모두 한 번 선택한 상태이며 반복 일관성 확인은 아니다.
- 두 맞춤 조건의 네 선호 규칙은 문자열 대조로 동일했다. 비교 출처 안내만 다르다. 직접 설정은 우리 서비스의 네 설정이며 사람의 자유 작성 지침이 아니다.
- 평가: 기존 `benchmarks/react_task_sync/acceptance.test.mjs`의 9개 행동 검사. 생성 전에 해시를 고정했고 후보 수정 후 기준을 바꾸지 않았다. HTTP는 모의 응답, React는 JSDOM에서 실행한다.
- 작업 폴더는 분리하고 서로의 결과·평가 파일을 읽지 않도록 지시했다. OS 수준 완전 격리는 아니다. 기존 의존성은 공유했다.

## 원자료와 재현

[고정 프로토콜·실제 프롬프트](results/2026-11-09/protocol.json), [결과·실측 시각](results/2026-11-09/summary.json),
[일반 패치](results/2026-11-09/arm_a.patch), [직접 설정 패치](results/2026-11-09/arm_b.patch), [예시 비교 패치](results/2026-11-09/arm_c.patch).
같은 폴더에 전체 과제 프롬프트, 원본/세 후보의 TAP 로그, 에이전트 자체 작성 테스트도 보존한다.

`run.py`는 준비·평가·수집을 담당한다. 에이전트 생성 자체를 자동 실행하지 않는다.

```powershell
.venv/Scripts/python.exe -m benchmarks.coding_prompt_routes.run prepare
# 수정 전 baseline을 먼저 평가한다.
.venv/Scripts/python.exe -m benchmarks.coding_prompt_routes.run baseline --reviewed
# 이후 독립 에이전트 실행과 후보 코드 검토를 마친다.
.venv/Scripts/python.exe -m benchmarks.coding_prompt_routes.run arm_a --reviewed
.venv/Scripts/python.exe -m benchmarks.coding_prompt_routes.run arm_b --reviewed
.venv/Scripts/python.exe -m benchmarks.coding_prompt_routes.run arm_c --reviewed
.venv/Scripts/python.exe -m benchmarks.coding_prompt_routes.run collect
```

기존 `.venv`와 설치된 `frontend/node_modules`를 사용한다. 각 복사본에는 읽기 전용으로 사용할 기존 의존성 경로 연결이 필요하다.
기존 실행 디렉터리·평가 결과가 있으면 준비·평가를 거절한다. 새 실행에는 RUN/DEST를 새 식별자로 바꾸고 새 프로토콜을 만든다.
당시 조건을 정확히 복원하려면 고정 커밋과 보존된 프롬프트를 사용한다. 최신 코드로 `prepare`를 실행하면 새 프로토콜이다.

이 결과는 짧은 비교 지침으로 작업할 수 있음을 보여 주지만, 예시 방식이 직접 설정보다 선호를 잘 찾거나 사람의 시간을 줄인다는 증거는 아니다.
별도 유료 API 요청은 없었으며 Codex 사용량·실제 계정 청구 내역은 이 실행에서 측정하지 않았다.
[선택 흐름 검증과 수정 보고](../../docs/history/2026-11-09_adaptive_validation.md).
