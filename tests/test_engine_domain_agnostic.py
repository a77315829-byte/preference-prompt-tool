"""절대 규칙 1: engine/ 은 도메인을 모른다. API 없이 돈다.

엔진 코드의 문자열 상수(독스트링·주석 제외)에 도메인 이름이나 축 이름이 나오면
엔진이 특정 도메인을 알고 분기한다는 뜻이다. 이름 수준의 검사라서 프롬프트 문구로
분기하는 경우는 못 잡는다 - 2026-10-13 에 생성기가 코딩 프롬프트의 제목 문구를 보고
출력 상한을 고르던 것이 그랬다. 그 경로는 domains/coding.yaml 의 max_output_tokens 로
옮겼고 tests/test_errors_and_limits.py 가 따로 본다.
"""

import ast
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def _domain_words() -> set[str]:
    words = set()
    for path in (ROOT / "domains").glob("*.yaml"):
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if raw.get("domain"):
            words.add(raw["domain"])
        words.update(axis["name"] for axis in raw.get("axes") or [])
    return words


def _string_constants(tree: ast.AST):
    docstrings = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and body:
            first = body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                docstrings.add(id(first.value))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
            yield node


def test_engine_code_names_no_domain_or_axis() -> None:
    words = _domain_words()
    assert {"coding", "summarization", "length"} <= words  # 목록이 비어 통과하지 않게
    found = []
    for path in sorted((ROOT / "engine").glob("*.py")):
        for node in _string_constants(ast.parse(path.read_text(encoding="utf-8"))):
            hits = sorted(word for word in words if word in node.value)
            if hits:
                found.append(f"{path.name}:{node.lineno} {hits}")
    assert found == []
