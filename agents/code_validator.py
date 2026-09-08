"""LLM이 생성한 measure() 함수 코드를 실행 전에 검증한다.

CLAUDE.md v2 절대 규칙 9: 에이전트가 생성한 코드는 검증 후에만 실행한다.

정적 검증(AST 기반)이 1차 방어선이다 - 계약(시그니처)을 지키는지, import나
위험한 이름·속성에 접근하지 않는지 확인한다. 2차 방어선은
agents/sandbox.py의 프로세스 격리 + 타임아웃이다. 이 모듈은 실행하지
않는다 - 실행해도 되는지만 판단한다.

import 문 자체를 전면 금지한다 (허용 목록 방식보다 안전): `import` 문은
`__import__` 빌트인을 필요로 하는데, 그걸 네임스페이스에 넣으면 우회
경로(`__import__('os')`)가 생긴다. 대신 안전한 모듈(re, math, statistics)은
sandbox.py가 실행 전에 이름공간에 미리 바인딩해준다.
"""

from __future__ import annotations

import ast
import re

REQUIRED_ARGS = ["text", "source"]

FORBIDDEN_NAMES = {
    "eval", "exec", "compile", "__import__", "open", "input",
    "globals", "locals", "vars", "getattr", "setattr", "delattr",
    "exit", "quit", "breakpoint", "help", "dir", "id", "memoryview",
}

_DUNDER_RE = re.compile(r"^__.+__$")


class ValidationError(Exception):
    pass


def validate_measure_code(code: str, function_name: str = "measure") -> None:
    """measure(text, source) -> float 형태인지, 위험한 코드가 없는지 검증한다.
    문제가 있으면 ValidationError를 던진다. 통과해도 "안전이 보장"되는 건
    아니고 "알려진 위험 패턴이 없다"는 뜻이다 - 그래서 sandbox.py의 프로세스
    격리가 실제 방어선이다."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        raise ValidationError(f"구문 오류: {e}") from e

    func_defs = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == function_name
    ]
    if not func_defs:
        raise ValidationError(f"'{function_name}' 함수 정의가 없음")
    if len(func_defs) > 1:
        raise ValidationError(f"'{function_name}' 함수가 여러 번 정의됨")

    func = func_defs[0]
    arg_names = [a.arg for a in func.args.args]
    if arg_names != REQUIRED_ARGS:
        raise ValidationError(f"시그니처가 {tuple(REQUIRED_ARGS)}가 아님: {arg_names}")

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            raise ValidationError(
                "import 문은 금지됨 - re/math/statistics/collections는 이미 "
                "이름공간에 들어있으므로 바로 쓰면 됨"
            )
        if isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
            raise ValidationError(f"금지된 이름 사용: {node.id}")
        # 던더(__x__) 이름/속성은 통째로 금지한다 (허용 목록 대신 패턴으로) -
        # ().__class__.__base__.__subclasses__() 류의 샌드박스 탈출 경로가
        # 전부 던더 체인이라, 개별 이름을 나열하는 것보다 구조적으로 막는
        # 쪽이 안전하다.
        if isinstance(node, ast.Name) and _DUNDER_RE.match(node.id):
            raise ValidationError(f"던더 이름 접근 금지: {node.id}")
        if isinstance(node, ast.Attribute) and _DUNDER_RE.match(node.attr):
            raise ValidationError(f"던더 속성 접근 금지: {node.attr}")
        if isinstance(node, (ast.Global, ast.Nonlocal)):
            raise ValidationError("global/nonlocal 사용 금지")
