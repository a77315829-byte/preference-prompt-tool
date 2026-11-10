# 검증 가능한 코딩 지침 v1 — 오프라인 프로토타입

[최종 목표와 개발 완료 기준](../../docs/coding-verifiable-goal.md)에 맞춰, 명시적 선택을 프롬프트로 만들고 받은 답변의 제한된 조건을 검사한다. 현재 웹 앱의 4항목 지침 생성기를 교체하지 않은 별도 모듈이다.

- 설명: `none`(코드만), `brief`(목록 1~3항목), `steps`(순서 목록 3~5항목).
- 전달: `markdown`(파일 제목과 단일 TSX 코드 블록), `json`(files/explanation 객체).
- 범위: TypeScript/React의 단일 `Component.tsx`, 이름 있는 export 함수 컴포넌트.
- 검사: 전달 구조, 설명 수/형식, TSX 구문 분석, 명시적 any, 제한된 import, export 함수 선언 단서.

이 숫자와 형식은 프로젝트의 검사 가능한 계약이다. 최적의 설명 길이·선택 횟수라는 연구 결과가 아니다. JSON 전달은 도구 연계용 형식 선택이며 제품의 기존 ‘변경 부분 중심’ 설정과 같지 않다.

## 실행

저장소 루트, 기존 `frontend/node_modules/typescript`만 사용한다. 새 의존성·서버·API 키가 필요 없다.

```powershell
node benchmarks/coding_contract_v1/contract.mjs prompt brief markdown
node benchmarks/coding_contract_v1/contract.mjs prompt steps json
node benchmarks/coding_contract_v1/contract.mjs inspect brief markdown path/to/answer.txt
node --test benchmarks/coding_contract_v1/contract.test.mjs
```

생성한 지침 아래에 새 작업을 별도로 전달한다. [실제 생성한 예시 지침](example-prompt.md)은 `brief/markdown` 설정이며 특정 작업 내용은 포함하지 않는다.

## 결과 해석

`contractSatisfied`는 구현한 검사 항목의 통과 여부다. `functionalCorrectness`와 `typeCorrectness`는 항상 `not_run`, `semanticQuality`는 `not_measured`, `jointSuccess`는 `null`이다. 컴포넌트 선언을 찾았다는 사실은 React 이벤트가 동작하거나 작업의 인터페이스가 맞는다는 뜻이 아니다. 타입 검사도 하지 않는다. 생성 코드를 import/eval/실행하지 않으며 `.env`·사용자 DB를 읽지 않는다.

프로토타입이 허용하는 코드 표현은 제한적이다. 익명 default export, 클래스 컴포넌트, re-export, 다중 파일 등은 지원하지 않는다. 자동 판정할 수 없는 의미적 품질, 코드의 안전성, 주석의 적절성은 검사 점수에 포함하지 않는다. 선언만 흉내 낸 코드가 통과할 가능성도 있으므로 별도 기능 검사가 필수다.

2026-11-10에 [테스트 12개](test-results.tap)가 통과했다. 6개 설정 조합과 잘못된 설명·JSON·구문·import·export 사례를 대조했다. 클릭 동작이 전혀 없는 버튼도 형식은 통과할 수 있으며 이때 기능 성공으로 표시되지 않는지 별도로 확인했다. **이는 검사기의 동작 확인이지 모델 생성 성능이나 사람의 평가 결과가 아니다.**

다음 단계는 개발 과제와 독립 기능 정답 검사를 준비하고, 같은 모델의 일반·직접 지침·조립 지침 결과를 평가하는 것이다. 논문 근거, 과제 분할, 비용 조건은 위 목표 문서에 있다.
