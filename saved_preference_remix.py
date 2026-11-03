"""저장 당시 개인·팀 값을 다시 조합한다. 현재 팀이나 원본 항목을 조회하지 않는다."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json

from engine.generator import build_final_prompt
from preference_comparison import _task_wording
import service


def remix_saved_prompt(item: dict, domain, choices: dict) -> dict:
    origin = item.get("provenance")
    if not origin or origin.get("version") != 1:
        raise ValueError("선택 출처 기록이 없어 다시 조합할 수 없어요. 팀과 비교해 새로 조합·저장해 주세요.")
    if not item.get("provenance_matches"):
        raise ValueError("저장 후 지침 본문·종류가 바뀌어 당시 선택과 맞지 않아요. 팀과 비교해 새로 조합해 주세요.")
    axes = origin["axes"]
    expected_axes = {a.name for a in domain.axes if a.type == "enum"}
    if len(axes) != len(expected_axes) or {a["axis"] for a in axes} != expected_axes:
        raise ValueError("저장 당시 항목 구성이 달라졌어요. 팀과 비교해 새로 조합해 주세요.")
    differing = {a["axis"] for a in axes if a["personal_value"] != a["team_value"]}
    if not isinstance(choices, dict) or set(choices) != differing or any(v not in ("personal", "team") for v in choices.values()):
        raise ValueError("서로 다른 모든 항목에서 내 선호 또는 팀 기준을 하나씩 골라 주세요.")
    old_combo = {a["axis"]: a["value"] for a in axes}
    languages = [origin["language"]] if origin.get("language") else service.prompt_languages(domain)
    language = next((lang for lang in languages if lang in service.prompt_languages(domain) and
                     _task_wording(domain, build_final_prompt(domain, old_combo, language=None if lang == "ko" else lang), lang).strip()
                     == item["prompt"].replace("\r\n", "\n").strip()), None)
    if language is None:
        raise ValueError("현재 구성으로 저장한 지침을 재현할 수 없어요. 팀과 비교해 새로 조합해 주세요.")
    provenance = deepcopy(origin)
    for axis in provenance["axes"]:
        source = choices.get(axis["axis"], "shared")
        axis["source"] = source
        axis["value"] = axis[f"{source if source != 'shared' else 'personal'}_value"]
    combo = {a["axis"]: a["value"] for a in provenance["axes"]}
    prompt = _task_wording(domain, build_final_prompt(domain, combo, language=None if language == "ko" else language), language)
    provenance.update(language=language, remixed_from={"title": item["title"], "revision": item["revision"],
        "axes": [{k: a[k] for k in ("axis", "label", "value", "source")} for a in axes]})
    provenance.pop("prompt_sha256", None)
    provenance.pop("domain_key", None)
    snapshot = {"id": item["id"], "revision": item["revision"], "choices": choices, "prompt": prompt}
    return {"prompt": prompt, "choices": choices, "provenance": provenance,
            "snapshot": hashlib.sha256(json.dumps(snapshot, sort_keys=True, ensure_ascii=False).encode()).hexdigest()}
