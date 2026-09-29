"""agents/sandbox.py가 별도 프로세스로 띄우는 실행기.

stdin으로 {code, text, source} JSON을 받아, code_validator로 다시 검증한
뒤(defense in depth - sandbox.py도 실행 전에 검증하지만 여기서도 한 번 더),
제한된 이름공간에서 measure(text, source)를 실행해 결과를 stdout에 JSON
으로 낸다. 프로세스가 별도이므로 여기서 죽어도(무한루프, 크래시) 부모
프로세스는 timeout으로 감지해 회수한다 - 이게 실제 격리 방어선이다.
"""

from __future__ import annotations

import builtins
import collections
import json
import math
import re
import statistics
import sys
from types import SimpleNamespace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.code_validator import MODULE_MEMBERS, ValidationError, validate_measure_code  # noqa: E402

_SAFE_BUILTIN_NAMES = (
    "len", "abs", "min", "max", "sum", "sorted", "reversed", "range",
    "enumerate", "zip", "map", "filter", "str", "int", "float", "bool",
    "list", "dict", "set", "tuple", "isinstance", "round", "any", "all",
)
SAFE_BUILTINS = {name: getattr(builtins, name) for name in _SAFE_BUILTIN_NAMES}


def main() -> None:
    payload = json.loads(sys.stdin.read())
    code, text, source = payload["code"], payload["text"], payload["source"]

    try:
        validate_measure_code(code)
    except ValidationError as e:
        print(json.dumps({"error": f"validation: {e}"}))
        return

    namespace: dict = {
        "__builtins__": SAFE_BUILTINS,
        # 실제 모듈을 넘기지 않는다. 별칭으로 받은 뒤에도 허용된 멤버만 보인다.
        **{
            name: SimpleNamespace(**{member: getattr(module, member) for member in MODULE_MEMBERS[name]})
            for name, module in {"re": re, "math": math, "statistics": statistics, "collections": collections}.items()
        },
    }
    try:
        exec(compile(code, "<measure>", "exec"), namespace)  # noqa: S102
        value = namespace["measure"](text, source)
        value = float(value)
        if not math.isfinite(value):
            raise ValueError("measure must return a finite number")
        print(json.dumps({"value": value}))
    except Exception as e:  # noqa: BLE001 - 샌드박스 실행기라 광범위 포착이 의도된 동작
        print(json.dumps({"error": f"{type(e).__name__}: {e}"}))


if __name__ == "__main__":
    main()
