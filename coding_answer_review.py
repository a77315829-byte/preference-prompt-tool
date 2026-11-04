"""Shared, non-executing answer inspection. Semantic preferences need a human."""
import ast
import io
import re
import tokenize

VERSION = 'coding-answer-review-v2'
MANUAL_KEYS = ('comments', 'structure')
STEP = re.compile(r'^\s*(?:#{1,6}\s+)?(?:\*\*)?(?:\d+[.)](?:\s|$)|\d+\s*단계\b|단계\s*\d+\b|[-*]\s+)', re.M)


def inspect_answer(profile, response, patch=None):
    if not isinstance(response, str) or not response.strip() or len(response) > 24000:
        raise ValueError('AI 답변을 1~24,000자로 붙여 넣어 주세요.')
    if patch is not None and type(patch) is not bool:
        raise ValueError('작업 유형을 확인해 주세요.')
    chunks = re.findall(r'```[^\n]*\n(.*?)```', response, re.S)[:8]
    prose = re.sub(r'```[^\n]*\n.*?```', '', response, flags=re.S).strip()
    markers = STEP.findall(prose)
    comments, definitions = [], []
    for code in chunks:
        if profile['language'].casefold() == 'python':
            try:
                comments.extend(token.string for token in tokenize.generate_tokens(io.StringIO(code).readline) if token.type == tokenize.COMMENT)
            except (tokenize.TokenError, IndentationError, SyntaxError):
                pass
            try:
                tree = ast.parse(code)
                definitions.extend(node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)))
            except (SyntaxError, ValueError, RecursionError):
                pass
        else:
            # Evidence only: skip ordinary quoted strings before collecting comment examples.
            token_pattern = r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|`(?:\\.|[^`\\])*`|/\*[\s\S]*?\*/|//[^\n]*'
            if profile['language'].casefold() in ('ruby', 'php'):
                token_pattern += r'|\#[^\n]*'
            comments.extend(m.group() for m in re.finditer(token_pattern, code) if m.group().startswith(('//', '/*', '#')))
            definitions.extend(re.findall(r'\b(?:class|interface|struct|function|func|fn|fun|def)\s+([\w]+)', code))
    files = re.findall(r'[\w./-]+\.(?:vue|py|java|[cm]?[jt]sx?|cs|cpp|cc|h|go|rs|kt|swift|dart|php|rb)\b', prose)
    explanation = len(prose) <= 400 if profile['preferences']['explanation'] == 'brief' else len(prose) >= 60 and bool(markers)
    return {
        'version': VERSION,
        'preferences': {'explanation': explanation, 'comments': None, 'structure': None, 'output': None},
        'manual_required': ['comments', 'structure', 'output'],
        'observations': {
            'explanation': f'코드 밖 설명 {len(prose)}자 · 제목 포함 단계/목록 표시 {len(markers)}곳',
            'comments': '발견한 주석 예시: ' + (' / '.join(c.strip()[:180] for c in comments[:3]) or '인식한 주석 없음') + ' · 개수로 적절함을 판정하지 않음',
            'structure': '선언·파일 단서: ' + (', '.join(dict.fromkeys((definitions + files)[:12])) or '자동으로 식별한 단서 없음') + (' · 기존 코드의 변경 부분이므로 생략된 구조를 부족으로 판단하지 않음' if patch else '') + ' · 역할과 규모의 적절함은 직접 확인',
            'output': ('기존 코드 변경 작업' if patch else '새 구현 작업' if patch is False else '작업 유형 미지정') + ' · 필요한 코드와 적용 위치가 충분한지 직접 확인',
        },
        'guidance': {
            'explanation': '해결 순서와 선택 이유를 이해할 수 있나요?' if profile['preferences']['explanation'] == 'steps' else '필요한 핵심을 빠르게 파악할 수 있나요?',
            'comments': '핵심 로직·입력 검증·주의점의 이유를 설명하나요? 문법을 그대로 반복하는 주석은 아닌가요?' if profile['preferences']['comments'] == 'detailed' else '코드만으로 알기 어려운 의도에만 주석이 있고 불필요한 반복이 적나요?',
            'structure': '입력 처리와 핵심 로직 등의 역할이 구분되고 실제로 연결되나요? 작은 변경에 불필요한 계층을 만들지 않았나요?' if profile['preferences']['structure'] == 'modular' else '작업 규모에 맞게 한눈에 읽히고 불필요한 계층·중복이 적나요?',
            'output': '수정 위치와 바뀐 코드가 충분한가요? 새 구현이면 필요한 전체 코드가 있나요?' if profile['preferences']['output'] == 'changes' else '필요한 파일과 코드가 빠짐없이 있어 적용할 수 있나요?',
        },
    }


def validate_human_review(raw, task_ids, changed):
    if raw is None:
        return {}
    if not isinstance(raw, dict) or len(raw) > len(task_ids):
        raise ValueError('직접 확인 기록의 형식을 확인해 주세요.')
    result = {}
    for task_id, sides in raw.items():
        if task_id not in task_ids or not isinstance(sides, dict) or not sides or len(sides) > 2:
            raise ValueError('확인할 과제가 일치하지 않아요.')
        result[task_id] = {}
        for side, choices in sides.items():
            if side not in (('original', 'candidate') if changed else ('original',)) or not isinstance(choices, dict) or len(choices) > 4:
                raise ValueError('확인할 답변이 일치하지 않아요.')
            if any(key not in ('explanation', 'comments', 'structure', 'output') or value not in ('match', 'needs_work', 'unsure') for key, value in choices.items()):
                raise ValueError('직접 고른 확인 결과만 저장할 수 있어요.')
            result[task_id][side] = dict(choices)
    return result
