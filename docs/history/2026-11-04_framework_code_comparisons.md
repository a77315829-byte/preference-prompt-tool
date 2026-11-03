# 선택한 프레임워크의 코드 예시 비교

기본 문법 비교에 Python/FastAPI와 Java/Spring Boot API 예시를 추가했다. 기존 React 비교·개인 보관함은 유지한다.

- `coding_framework_examples.py`에 준비된 두 프레임워크의 `GET /orders/total` 예시를 둔다. 같은 요청 경로·입력·응답을 유지하며 설명, 주석, 파일 구성, 전체/변경 코드의 네 항목을 비교한다.
- FastAPI는 `main.py` 한 파일과 `main.py` + `orders.py`의 APIRouter 구조를 비교한다. Spring Boot는 `OrderController.java` 한 파일과 컨트롤러 + `OrderService.java` 구조를 비교한다.
- 파일 이름과 전체 코드, 출력 비교의 변경 전 코드 및 교체할 파일/한 줄을 표시한다. 복수 파일은 파일 이름 목록과 스크롤 영역으로 확인한다.
- 비교 출처 version 2는 예시 ID·종류·이름을 기록하고 서버에서 현재 언어·프레임워크와 대조한다. 결과 지침과 보관함에도 예시 이름이 남는다. 기존 version 1 저장본은 기본 문법 비교로 유지한다.
- 새 결과를 저장·재사용해도 원래 저장본은 갱신하지 않는다. 환경·선호를 직접 변경하면 비교 출처를 초기화하는 기존 동작을 유지한다.
- Django 등 아직 전용 예시가 없는 조합은 해당 프레임워크 전용 코드가 아닌 언어 기본 문법 예시임을 명시한다. 버전 문자열을 임의로 해석해 지원한다고 표시하지 않는다.
- 새 의존성·DB migration·엔진 변경·유료 API 호출이 없다. 예시를 UI에서 실행하는 기능은 추가하지 않았다.

검증은 관련 Python 72개, 프론트 전체 68개와 Vite 빌드를 통과했다. FastAPI 코드는 AST로 문법·경로 연결·입력 선언을 확인하고 경로 함수의 계산만 분리해 두 구조와 변경 결과가 같은지 검사했다. 이 환경에 FastAPI 패키지와 Java 도구가 없어 실제 프레임워크 서버 실행이나 Java 컴파일 검증을 수행했다고 주장하지 않는다.

참고한 공식 문서:

- [FastAPI: APIRouter와 여러 파일로 구성하기](https://fastapi.tiangolo.com/tutorial/bigger-applications/)
- [Spring: REST 서비스의 컨트롤러·매개변수·JSON 응답](https://spring.io/guides/gs/rest-service/)

기존 미리보기 DB를 사용하는 실제 브라우저에서 Spring Boot 예시와 FastAPI 파일 분리 비교를 확인했다. FastAPI 결과를 예시 계정의 새 보관 항목에 저장하고 다시 열어 예시 이름과 선택 출처가 유지됨을 확인했다. 기존 저장본 및 운영 DB는 덮어쓰지 않았다.
