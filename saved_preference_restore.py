"""비교에서 선택한 항목만 직전 방식으로 복원한 새 항목의 지침을 만든다."""
from __future__ import annotations

import hashlib
import json

from saved_preference_remix import remix_saved_prompt


def restore_saved_prompt(item: dict, domain, selected_axes: list) -> dict:
    origin = item.get("provenance") or {}
    before = origin.get("remixed_from") or {}
    if not isinstance(before.get("axes"), list):
        raise ValueError("바꾸기 전 항목 기록이 없어 되돌릴 수 없어요. 저장한 선택을 다시 조합해 주세요.")
    current = {a["axis"]: a for a in origin["axes"]}
    previous = {a["axis"]: a for a in before["axes"]}
    if set(previous) != set(current) or len(previous) != len(before["axes"]):
        raise ValueError("변경 전·후 항목 기록이 맞지 않아 되돌릴 수 없어요.")
    changed = {axis for axis, a in current.items()
               if a["value"] != previous[axis]["value"] or a["source"] != previous[axis]["source"]}
    if (not isinstance(selected_axes, list) or not selected_axes or any(not isinstance(a, str) for a in selected_axes)
            or len(set(selected_axes)) != len(selected_axes) or not set(selected_axes) <= changed):
        raise ValueError("바뀐 항목 중 되돌릴 항목을 하나 이상 골라 주세요.")
    choices = {axis: a["source"] for axis, a in current.items() if a["personal_value"] != a["team_value"]}
    for axis in selected_axes:
        old = previous[axis]
        source = old["source"]
        if source not in ("personal", "team") or current[axis].get(f"{source}_value") != old["value"] or axis not in choices:
            raise ValueError("기록된 이전 방식으로 되돌릴 수 없는 항목입니다. 저장한 선택을 다시 조합해 주세요.")
        choices[axis] = source
    draft = remix_saved_prompt(item, domain, choices)
    selected = [a.name for a in domain.axes if a.name in selected_axes]
    snapshot = {"operation": "restore", "base": draft["snapshot"], "axes": selected}
    draft["snapshot"] = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
    draft["restore_axes"] = selected
    draft["provenance"]["operation"] = "restore"
    return draft
