# 2026-11-04 환경별 GEPA 확장 4차: Next.js

## 연결 범위

JavaScript/Next.js·TypeScript/Next.js를 GEPA 전후 비교·직접 판단·새 항목 저장·재사용 흐름에 연결했다. JavaScript 프레임워크 카드에도 Next.js를 추가했다. 전체 지원은 12조합이며 원본 개인 지침·기존 저장 항목·팀 기준을 덮어쓰지 않는다. 더 나은 후보가 없으면 기존 원본 유지 흐름을 사용한다.

이번 평가는 App Router GET API에 한정한다. 기존 React 평가를 이름만 바꿔 적용하지 않고 `nextjs_coding_evaluation.py`에 별도 개선용 2개·후보 선택용 2개·별도 확인용 2개를 두었다. 평가 버전은 `nextjs-route-ast-v2`이며 JavaScript/TypeScript의 캐시를 나눈다. 실행 플래그는 기존 `PPT_WEB_GEPA_LIVE`이고 Node.js·프론트 TypeScript 의존성과 모델 설정이 준비된 환경에서만 시작할 수 있다.

계정 소유권·공유 하루 한도·동시 실행 제한·작업당 최대 32회 요청/성찰 4회·서버 결과만 새 항목으로 저장하는 기존 경로를 사용한다. 새 라이브러리·DB migration·`engine/` 변경은 없다. Next.js 패키지를 평가 서버에 설치하지 않는다.

## 과제와 평가

- 코드 블록 바로 위에 제시한 `app/.../route.ts/js` 또는 `src/app/...` 위치와 export GET을 확인한다. 실제 파일을 만들거나 HTTP 라우팅을 실행하지 않는다.
- `request.nextUrl.searchParams`와 `new URL(request.url).searchParams`로 읽는 필수 숫자 쿼리를 다룬다. 양쪽 입력의 누락·빈 문자열·공백·비숫자·무한대·음수에 JSON 400 오류를 반환하는지 확인한다.
- next/server의 NextResponse import/별칭 또는 Web Response.json의 JSON 키·상태·세 정상 입력 계산값을 확인한다. 별도 순수 계산 함수와 답변에 포함된 import 연결을 다룬다.
- 변경 부분 선호는 export 없는 GET 함수 전체 또는 마지막 return을 제공된 기존 파일 맥락에서 해석한다. 필요한 import·계산 함수가 있어도 부분 수정으로 확인한다. 전체 파일 선호는 경로 제목과 export GET을 포함한다.
- 기존 TypeScript 파서와 제한된 AST 해석기를 확장했다. 생성된 코드나 모듈을 import/eval하지 않는다. URL·숫자·trim·JSON 응답은 허용된 AST 노드와 내부 모델만 사용한다. 노드·깊이·명령 수와 6초 제한을 유지한다.
- 주석·역할 구성은 개수로 점수화하지 않는다. 사용자가 실제 답변을 보고 네 선호를 직접 판단하고 새 후보에 함께 저장한다.

실제 Next.js 빌드·서버·화면·캐싱·타입·보안·모듈 경로 해결·일반적인 정확성 검증이 아니다. Pages Router·동적 경로·Server Actions는 별도 지원하지 않는다. 다른 올바른 문법도 허용된 범위 밖이면 자동 미확인될 수 있으며 준비 과제 점수로 일반적인 개인화 효과를 주장하지 않는다.

## 검증

Next.js 기본 검사 9개는 두 언어의 전체/부분 답변, 파일·메서드·export·입력·오류 상태·빈 값·계산 오류, import 별칭과 URL 접근, 별도 계산 함수, 가짜/타입 전용 import, 예약 이름 가림과 위험한 코드의 비실행을 확인했다. 설치된 실제 GEPA 엔진에 테스트 모델을 연결해 후보 탐색·과제 분리·캐시·고정 원본·직접 판단의 새 저장도 확인했다.

관련 Python 회귀 검사 95개(Next.js HTTP 검사 포함), 프론트 전체 83개 검사와 Vite 빌드가 통과했다. 두 언어 모두 비교→직접 판단→채택→새 저장→재열람→새 작업 재사용을 검사했고, 다른 환경이 켜져 있어도 Next.js의 기능 설정이 없으면 시작하지 못함을 확인했다.

로컬 예시 계정에서 TypeScript/Next.js 선택과 네 선호·프롬프트 생성·환경별 검사 범위·활성화한 시작 버튼을 확인했다. 화면 증거는 Git에 넣지 않는 `data/nextjs-gepa-ready.jpg`다. 예시 DB의 기존 보관 항목 15개는 전체 행 해시가 유지됐다. 이번 연결 확인에서는 새 유료 모델 호출을 하지 않았으며 실제 모델의 개인화 효과 검증은 후속 과제다.

## 근거와 다음 연결

공식 [Route Handlers 파일 규칙](https://nextjs.org/docs/app/api-reference/file-conventions/route)과 [NextResponse.json](https://nextjs.org/docs/app/api-reference/functions/next-response)을 기준으로 준비 과제의 인터페이스를 정했다. 실제 프레임워크 전체 동작을 재현했다는 의미는 아니다.

다음 대상은 NestJS다. NestJS의 컨트롤러·쿼리·검증·서비스 연결은 독립 과제를 추가한 뒤 지원 목록에 올린다.
