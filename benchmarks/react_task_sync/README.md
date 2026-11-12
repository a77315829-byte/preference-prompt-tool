# 실제 React 작업 요청 동기화 버그: Codex 독립 비교

`3b6b550`의 실제 UI 버그를 대상으로 일반 지침과 프로젝트 생성 지침을 비교하는 **1과제 × 조건당 1회** 파일럿이다.
코드베이스는 React JSX이므로 TypeScript 컴파일 정확도를 측정했다고 표현하지 않는다.

2026-11-09 결과: 일반 **156.737초·9/9**, 맞춤 **166.895초·9/9**. 기능 차이는 없었고 이번 실행에서는 맞춤이 약 10초 길었다. 사람의 수정 시간은 미측정이다. [전체 해석과 한계](../../docs/history/2026-11-09_react_bug_prompt_comparison.md), [원자료](results/2026-11-09/summary.json).

## 실험 구성

`prepare.py`는 Git 커밋에서 동일한 프론트엔드 두 벌과 동일한 저장소 지침을 별도 작업 폴더로 복사한다.
일반 지침은 `coding_work_trials.general_prompt`, 맞춤 지침은 `coding_instructions.build_coding_instructions`로 생성한다.
공통 과제·완료 조건·검사 환경은 같고 추가 작성 선호만 다르다. 고정 선호는 실험자가 지정했으며 사용자의 8~10회 선택 효과를 시험하는 실험이 아니다.

사용자가 명시적으로 승인한 두 보조 에이전트는 부모 대화 이력 없이 같은 모델 설정을 상속한다. 서로의 코드·평가기·결과를 읽지 않도록 작업 범위를 제한한다. 두 실행은 같은 호스트에서 동시 진행되어 자원 경쟁이 시간에 영향을 줄 수 있다. 계정 API 키를 이용하는 별도 모델 호출은 실행하지 않는다.

`protocol.json`은 생성 전에 고정한 기준 커밋·검사 해시·타이밍 정의를 담는다.
`acceptance.test.mjs`는 모델 답을 평가하는 LLM을 쓰지 않고 실제 React 컴포넌트를 JSDOM에서 렌더링한다. HTTP는 모의 응답이다.

검사 9개는 최초 입력, 늦은 부모 입력, 부모 변경/삭제, 직접 편집 보존, 명시적 빈 입력 보존, 원문으로 되돌린 직접 편집, 다른 필드 보존, 생성한 기록의 불변/새 비교 초기화, 저장 기록 재개/취소를 포함한다.
수정 전 기준 코드는 5/9 통과, R2·R3·R8·R9 실패다.

## 재현

기존 `.venv`와 `frontend/node_modules`를 사용하며 새 패키지는 설치하지 않는다.

```powershell
.venv/Scripts/python.exe -m benchmarks.react_task_sync.prepare
node --test benchmarks/react_task_sync/acceptance.test.mjs
```

준비 스크립트는 `tmp/react-task-sync-20261109`가 있으면 중단해 기존 실행을 덮어쓰지 않는다. 재현용 새 실행은 별도 ID/폴더와 프로토콜로 시작한다. 각 복사본의 `frontend/node_modules`에는 기존 설치 폴더를 읽기 전용으로 사용하는 디렉터리 연결이 필요하다.

부모가 실제 수정 코드를 검토한 뒤에만 다음 평가를 실행한다. 결과가 이미 있으면 재평가하지 않고 기존 기록을 보존한다.

```powershell
.venv/Scripts/python.exe -m benchmarks.react_task_sync.evaluate arm_a --reviewed
.venv/Scripts/python.exe -m benchmarks.react_task_sync.evaluate arm_b --reviewed
```

현재 작업 트리의 회귀 검사에는 환경변수 없이 `node --test benchmarks/react_task_sync/acceptance.test.mjs`를 사용한다. 다른 복사본에는 `PPT_REACT_BENCH_TARGET`을 해당 복사본의 `frontend` 절대 경로로 지정한다.

## 시간·정확도 해석

- **에이전트 작업 시간**: 첫 도구 호출에 저장한 실제 UTC 시각부터 마지막 도구 호출에 저장한 제출 시각까지. 분석·편집·자체 검사를 포함한다. 발송 전 준비와 첫 도구 전 모델 응답 지연은 포함하지 않는다.
- **독립 검사 시간**: 부모가 같은 고정 검사 명령을 실행한 경과 시간. 코드 생성 시간과 분리한다.
- **기능 정확도**: 미리 정한 9개 동작의 통과 수이며 전체 앱 품질·보안·브라우저 호환성 점수가 아니다.
- **사람의 수정 시간·선호**: 참여자가 없으므로 미측정(`null`). 0분으로 바꾸지 않는다.
- **인과 주장**: 표본 1개·반복 1회다. 더 빠르게 끝난 조건이 있더라도 프롬프트 덕분이라고 결론짓거나 사용자 생산성 향상으로 환산하지 않는다.

현재 Codex 안에서 이와 같은 소규모 비교를 진행할 수 있다. 별도 API 청구를 만들지 않는 실행과 Codex 자체 요금은 구분한다. ChatGPT 로그인은 구독 접근, API 키 로그인은 API 과금이며, 사용량/크레딧은 요금제에 따라 다르다. 이 실험은 계정 잔여 한도·실제 청구 내역을 조회하지 않는다. [공식 인증 안내](https://learn.chatgpt.com/docs/auth), [공식 요금 안내](https://learn.chatgpt.com/docs/pricing).
