"""개발자용 프롬프트 작업 공간 (docs/developer_prompt_workspace_plan.md 1차 MVP).

업무 설명 -> 요구사항 확인 -> 변수형 프롬프트 -> 샘플 입력으로 시험 -> 개발용
묶음 내보내기. 기존 선호 비교 루프(service.py)와 분리된 패키지이고(절대 규칙
10), engine/ · checks/ · domains/ · optimize/ 를 고치지 않는다.

Streamlit 을 import 하지 않는다. 서버는 상태를 들고 있지 않는다 - 프로젝트
JSON 을 화면이 들고 있다가 단계마다 보낸다. 그래서 재시작해도 잃는 것이 없고
서버 메모리도 늘지 않는다.
"""
