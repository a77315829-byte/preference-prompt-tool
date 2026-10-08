"""제한된 `{{variable_name}}` 치환과 입력 검증 (계획서 7절).

- 허용하는 문법은 `{{이름}}` 하나다. 필터·함수 호출·조건문이 없고 `eval` 도
  쓰지 않는다.
- 치환은 **한 번에** 한다 (`re.sub` 한 번). 값 안에 `{{other}}` 가 들어 있어도
  다시 평가하지 않는다 - 사용자 데이터가 템플릿이 되는 길을 막는다.
- 원시값이 아닌 값(목록·객체)은 JSON 문자열로 넣는다.

이 모듈은 외부 의존성이 없다. 내보내기 묶음의 render_example.py 가 같은
규칙을 쓰도록 `exports.py` 가 이 파일의 핵심 함수를 그대로 복사해 넣는다.
"""

from __future__ import annotations

import json
import re
from typing import Any

PLACEHOLDER = re.compile(r"\{\{\s*([a-z_][a-z0-9_]*)\s*\}\}")

_JSON_TYPES = {
    "string": (str,),
    "number": (int, float),
    "integer": (int,),
    "boolean": (bool,),
    "array": (list,),
    "object": (dict,),
}


def placeholders(template: str) -> list[str]:
    """템플릿에 나오는 변수 이름, 처음 나온 순서대로 중복 없이."""
    seen: list[str] = []
    for name in PLACEHOLDER.findall(template):
        if name not in seen:
            seen.append(name)
    return seen


def _type_ok(value: Any, kind: str) -> bool:
    # bool 은 int 의 하위 클래스라 숫자 자리에 true 가 통과하지 않게 따로 막는다.
    if kind in ("number", "integer") and isinstance(value, bool):
        return False
    return isinstance(value, _JSON_TYPES[kind])


def check_input(variables: list[dict[str, Any]], template: str, values: Any) -> list[dict[str, str]]:
    """모델을 부르기 전에 고칠 것들. 비어 있으면 렌더해도 된다.

    각 항목은 {"variable", "problem", "message"} 다. problem 은
    not_object / missing / wrong_type / undeclared 중 하나.
    """
    if not isinstance(values, dict):
        return [{"variable": "", "problem": "not_object",
                 "message": "시험 입력은 JSON 객체({ ... })여야 합니다."}]
    problems = []
    declared = {v["name"]: v for v in variables}
    for var in variables:
        name = var["name"]
        value = values.get(name)
        if value is None or (isinstance(value, str) and not value.strip()):
            if var.get("required"):
                problems.append({"variable": name, "problem": "missing",
                                 "message": f"필수 변수 '{name}' 의 값이 없습니다."})
            continue
        if not _type_ok(value, var["type"]):
            problems.append({"variable": name, "problem": "wrong_type",
                             "message": f"'{name}' 은 {var['type']} 이어야 합니다."})
    for name in placeholders(template):
        if name not in declared:
            problems.append({"variable": name, "problem": "undeclared",
                             "message": f"템플릿의 {{{{{name}}}}} 가 변수 목록에 없습니다."})
    return problems


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def render(template: str, values: dict[str, Any]) -> str:
    """`{{이름}}` 을 값으로 바꾼다. 없는 이름은 빈 문자열이 된다 -
    호출하는 쪽이 `check_input` 으로 먼저 걸러야 한다."""
    return PLACEHOLDER.sub(lambda m: _as_text(values.get(m.group(1))), template)


def build_messages(system_prompt: str, input_template: str, values: dict[str, Any]) -> list[dict[str, str]]:
    """지침과 요청 데이터를 서로 다른 메시지로 나눈다. 나눈다고 프롬프트
    인젝션이 해결되는 것은 아니다 (계획서 7절) - 섞지 않을 뿐이다."""
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": render(input_template, values)},
    ]
