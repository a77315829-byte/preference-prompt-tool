"""Scoring contract shared by the bounded coding checks and their reports."""

FUNCTION_WEIGHT = 0.65
PREFERENCE_WEIGHT = 0.35


def weighted_score(checks, preferences, gate):
    automatic = [preferences[key] for key in ('explanation', 'output')]
    return round(FUNCTION_WEIGHT * sum(checks.values()) / 4
                 + PREFERENCE_WEIGHT * sum(value is True for value in automatic) / 2, 4) if checks[gate] else 0.0


def scoring_rules(kind, profile):
    java = kind == 'spring_boot'
    selected = profile['preferences']
    return {
        'function_weight': FUNCTION_WEIGHT, 'preference_weight': PREFERENCE_WEIGHT,
        'preference_keys': ['explanation', 'output'], 'manual_preferences': ['comments', 'structure'],
        'version': 'coding-preferences-v2',
        'gate': 'code_structure' if java else 'syntax',
        'checks': {
            ('code_structure' if java else 'syntax'): 'Java 코드의 제한된 토큰·괄호·클래스·메서드 구조 확인. 컴파일 검사는 아님.' if java else 'Python AST로 문법과 허용 크기 확인. 실행 검사는 아님.',
            'route': '요청한 GET 경로와 프레임워크 선언 확인.',
            'validation': '필수 정수 입력 연결 및 두 음수 입력 거절 패턴 확인.' if java else '두 입력에 Query(ge=0) 선언 확인.',
            'calculation': '세 입력 예시의 제한된 반환 계산식 확인. 전체 기능 검증은 아님.',
        },
        'preferences': {
            'explanation': '코드 밖 설명 400자 이하.' if selected['explanation'] == 'brief' else '코드 밖 설명 60자 이상이며 제목의 번호(### 1. 등), 단계 표시 또는 줄 시작 번호/목록 인식. 설명의 적절함은 직접 확인.',
            'comments': '직접 확인: 핵심 의도·주의점의 설명과 불필요한 반복을 실제 주석에서 확인. 개수로 점수화하지 않음.',
            'structure': '직접 확인: 역할의 구분·실제 연결·작업 규모에 맞는 구성을 확인. 함수·클래스 수로 점수화하지 않으며 변경 부분만 제시한 답변을 불리하게 취급하지 않음.',
            'output': ('기존 코드 변경 과제에서는 클래스 선언 없이 변경 부분, 새 구현에서는 클래스·import 포함.' if selected['output'] == 'changes' else '클래스·import를 포함한 전체 코드.') if java else ('기존 코드 변경 과제에서는 FastAPI import 없이 변경 부분, 새 구현에서는 FastAPI import 포함.' if selected['output'] == 'changes' else 'FastAPI import를 포함한 전체 코드.'),
        },
    }
