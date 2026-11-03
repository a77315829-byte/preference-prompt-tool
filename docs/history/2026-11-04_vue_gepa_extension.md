# 2026-11-04 환경별 GEPA 확장 3차: Vue

## 사용자 흐름

JavaScript/Vue·TypeScript/Vue를 기존 GEPA 흐름에 연결했다. TypeScript 프레임워크 선택 카드에도 Vue를 추가했다. 지원 환경은 총 10조합이다. 네 선호로 만든 원본 지침은 고정하고 GEPA가 보충 안내를 탐색한다. 사용자는 전후 지침과 별도 과제의 답변을 비교하고 직접 판단한 뒤, 이름을 붙인 새 보관 항목으로 저장해 다음 작업에서 재사용한다. 기존 저장 항목과 팀 기준을 갱신하지 않는다.

`PPT_WEB_GEPA_LIVE=1`이 React·Express와 함께 Vue 두 조합도 켠다. Node.js와 기존 TypeScript 의존성 및 모델 설정이 필요하며, 준비되지 않으면 비용이 드는 시작을 막는다. 계정별 소유권·공유 할당량·서버 결과 기반 저장·캐시·작업당 최대 32회 요청/성찰 4회 제한은 공통 경로를 따른다. 새 라이브러리·DB migration·`engine/` 변경은 없다.

## Vue 평가 범위

`vue_coding_evaluation.py`는 Vue 3 `<script setup>`과 숫자 `defineProps`, `computed`, `v-if/v-else`, 보간을 사용하는 독립 과제를 제공한다. 개선용 2개·후보 선택용 2개·별도 확인용 2개를 구분하고 환경별 `vue-ast-v2` 캐시를 쓴다. 주석·역할 구성은 개수로 점수화하지 않으며 실제 답변을 보고 판단한다. .vue 파일 이름도 직접 확인 단서에 표시한다.

기존 `scripts/check_web_coding.mjs`의 TypeScript 파서와 제한된 해석기를 확장했다. SFC의 script setup과 제한된 템플릿 구조를 읽고, 누락·비숫자·무한대·음수 입력에는 오류만 표시되는지, 정상 세 입력에는 지정 output의 계산값과 숨겨진 오류가 유지되는지 확인한다. computed 본문은 해당 분기에 필요할 때 해석해, 오류 분기에서 쓰지 않는 계산식 때문에 정상적인 오류 처리를 거절하지 않는다. 생성된 코드는 import/eval하지 않는다.

숫자 props는 JS의 `Number` 또는 `{ type: Number, required: true }`, TS의 인라인 숫자 타입을 다룬다. computed import 별칭·순수 계산 함수·제공된 별도 파일의 import 연결도 확인한다. 변경 과제는 script setup 또는 template 블록을 준비된 기존 코드 맥락에 적용한다. 둘 다 바뀌면 별도 코드 블록으로 제시하며, 필요한 import·계산 함수가 있어도 부분 수정으로 인식한다.

이는 Vue 컴파일러가 아니며 실제 Vue 컴파일·브라우저 렌더링·반응성·타입·보안·전체 품질 검증을 제공하지 않는다. Options API·외부 컴포넌트·이벤트·리스트·기타 지원 밖 문법은 올바르더라도 자동 미확인될 수 있다. 과제 점수를 일반적인 개인화 효과로 해석하지 않는다.

## 검증

- 관련 Python 회귀 검사 85개, 프론트 전체 83개와 Vite 빌드가 통과했다. 이후 props 선언·분리 블록 허용을 보완하고 Vue/React/Express 관련 검사 15개를 다시 확인했다(HTTP 2개는 앞선 회귀 검사에 포함).
- Vue 두 언어에서 전체/부분 답변, 잘못된 계산·오류 분기·출력 위치·props 선언·템플릿 구조, 별도 계산 함수와 computed 별칭, 가짜 import·위험한 코드의 비실행을 확인했다.
- 설치된 실제 GEPA 엔진에 테스트 모델을 연결해 탐색·원본 고정·별도 과제·환경별 캐시·한도와 새 보관 항목 저장/직접 판단 기록을 확인했다. 프론트는 두 언어에서 전후 비교·채택·새 저장·재열람·새 작업 재사용·미지원 설정 차단을 확인했다.
- 로컬 예시 계정 화면에서 TypeScript/Vue 선택→네 선호→프롬프트 생성→환경별 검사 범위와 활성화된 시작 버튼을 확인했다. 화면 증거는 Git에 넣지 않는 `data/vue-gepa-ready.jpg`다. 예시 DB의 기존 보관 항목 15개는 전체 행 해시가 유지됐다.
- 이번 연결 확인에서 새 유료 모델 호출은 하지 않았다. 실제 모델의 개선 효과·사용자 만족도 검증은 후속 과제다.

## 참고와 다음 범위

Vue 계약은 공식 [script setup](https://vuejs.org/api/sfc-script-setup.html), [computed](https://vuejs.org/guide/essentials/computed.html), [조건부 렌더링](https://vuejs.org/guide/essentials/conditional.html) 문서를 참고했다. computed의 캐싱·변경 반응성이나 Vue 전체 문법을 구현했다는 의미는 아니다.

다음 대상은 Next.js·NestJS다. 기존 React/Vue 지원으로 자동 승격하지 않고 각 환경의 별도 계약과 과제를 연결한 뒤 지원 목록에 추가한다.
