"""모델 출력이 출력 계약을 지키는지 코드로 잰다 (절대 규칙 6).

여기서 재는 것은 **형식**뿐이다 - JSON 으로 읽히는가, 필수 필드가 있는가,
타입과 배열 개수가 맞는가. 값이 맞는지(합계가 입력과 같은지 등)는 의미 검사이고
check_sets.py 의 몫이다. 화면에서도 두 묶음을 따로 보여 준다.

검사 결과는 늘 셋 중 하나다: pass / fail / not_evaluated. 실행하지 않은 것을
pass 로 적지 않는다 (계획서 5-C).
"""

from __future__ import annotations

import json
import re
from typing import Any

from prompt_workspace.renderer import _type_ok

_FENCE = re.compile(r"^```(?:json)?\s*\n(.*?)\n```\s*$", re.DOTALL)


def check(name: str, status: str, detail: str = "", group: str = "contract") -> dict[str, str]:
    assert status in ("pass", "fail", "not_evaluated")
    return {"name": name, "status": status, "detail": detail, "group": group}


def parse_output(text: str) -> tuple[Any, str]:
    """(값, 오류). 코드 블록 하나로 감싼 JSON 은 벗겨서 읽는다 - 모델이 자주
    그렇게 낸다. 그 경우도 detail 에 적어서 숨기지 않는다."""
    stripped = (text or "").strip()
    if not stripped:
        return None, "빈 출력"
    fenced = _FENCE.match(stripped)
    body = fenced.group(1) if fenced else stripped
    try:
        value = json.loads(body)
    except json.JSONDecodeError as exc:
        return None, f"JSON 으로 읽을 수 없음 ({exc.msg}, {exc.lineno}행)"
    return value, ("코드 블록을 벗겨서 읽음" if fenced else "")


def _check_fields(fields: list[dict], obj: dict, prefix: str) -> list[dict[str, str]]:
    results = []
    for field in fields:
        name = f"{prefix}{field['name']}"
        if field["name"] not in obj or obj[field["name"]] is None:
            if field["required"]:
                results.append(check(f"필드 {name}", "fail", "필수 필드가 없음"))
            continue
        value = obj[field["name"]]
        if not _type_ok(value, field["type"]):
            results.append(check(f"필드 {name}", "fail", f"{field['type']} 이어야 함"))
            continue
        if field["type"] != "array":
            results.append(check(f"필드 {name}", "pass"))
            continue
        lo, hi = field.get("min_items"), field.get("max_items")
        if lo is not None and len(value) < lo:
            results.append(check(f"필드 {name}", "fail", f"항목 {len(value)}개, 최소 {lo}개"))
            continue
        if hi is not None and len(value) > hi:
            results.append(check(f"필드 {name}", "fail", f"항목 {len(value)}개, 최대 {hi}개"))
            continue
        bad = []
        for i, item in enumerate(value):
            if field.get("item_type"):
                if not _type_ok(item, field["item_type"]):
                    bad.append(f"[{i}] {field['item_type']} 이 아님")
            elif not isinstance(item, dict):
                bad.append(f"[{i}] 객체가 아님")
            else:
                for sub in _check_fields(field["item_fields"], item, ""):
                    if sub["status"] == "fail":
                        bad.append(f"[{i}].{sub['name'].removeprefix('필드 ')} {sub['detail']}")
        results.append(check(f"필드 {name}", "fail" if bad else "pass", "; ".join(bad[:5])))
    return results


def check_output(contract: dict[str, Any], text: str) -> tuple[Any, list[dict[str, str]]]:
    """(읽은 값 또는 None, 검사 목록). 파싱에 실패하면 필드 검사는 실행하지
    않았으므로 not_evaluated 로 남긴다."""
    fields = contract.get("fields", [])
    value, note = parse_output(text)
    if value is None:
        results = [check("JSON 파싱", "fail", note)]
        results += [check(f"필드 {f['name']}", "not_evaluated", "파싱 실패로 검사 안 함") for f in fields]
        return None, results
    if not isinstance(value, dict):
        return value, [check("JSON 파싱", "fail", "최상위가 객체가 아님")]
    results = [check("JSON 파싱", "pass", note)]
    if not fields:
        results.append(check("출력 계약", "not_evaluated", "정의된 필드가 없음"))
    results += _check_fields(fields, value, "")
    return value, results
