"""저장된 개인 지침과 현재 팀 기준 비교. 모델 호출이나 원본 변경은 하지 않는다."""
from __future__ import annotations

from dataclasses import asdict
import hashlib
from itertools import product
import json

from engine.generator import build_final_prompt
import service
import team


def recognize_standard_prompt(domain, prompt: str):
    """기본 생성문 전체가 일치할 때만 축을 확인한다. 수정·최적화 문구는 추측하지 않는다."""
    options = [["", *[v.value for v in a.values]] if a.type == "enum" else [""] for a in domain.axes]
    count = 1
    for values in options:
        count *= len(values)
    if count > 2000:
        return None
    normalized = prompt.replace("\r\n", "\n").strip()
    for language in service.prompt_languages(domain):
        for values in product(*options):
            combo = dict(zip((a.name for a in domain.axes), values))
            candidate = build_final_prompt(domain, combo, language=None if language == "ko" else language)
            if candidate.strip() == normalized:
                return {"combo": combo, "language": language}
    return None


def team_basis(domain, code: str, members: list, language: str) -> dict:
    if language not in service.prompt_languages(domain):
        raise ValueError("지원하지 않는 지침 언어입니다.")
    if not members:
        raise ValueError("아직 선호를 합친 팀원이 없어요. 팀에서 선호를 모은 뒤 다시 확인해 주세요.")
    estimator, agreements = team.summarize(domain, members)
    prompt = service.final_prompt(domain, estimator, team=True, language=language)
    snapshot = {"code": code, "domain": domain.name, "language": language, "prompt": prompt,
                "agreements": [asdict(a) for a in agreements], "members": len(members)}
    return {"prompt": prompt, "combo": service.final_combo(domain, estimator), "agreements": agreements,
            "snapshot": hashlib.sha256(json.dumps(snapshot, sort_keys=True, ensure_ascii=False).encode()).hexdigest()}


def compare_preferences(item: dict, domain, code: str, name: str, members: list, language: str | None = None) -> dict:
    personal = recognize_standard_prompt(domain, item["prompt"])
    languages = service.prompt_languages(domain)
    language = language or (personal["language"] if personal else ("en" if "en" in languages else languages[0]))
    basis = team_basis(domain, code, members, language)
    axes = []
    labels = domain.final_prompt.axis_labels if domain.final_prompt else {}
    for agreement in basis["agreements"]:
        mine = personal["combo"].get(agreement.axis, "") if personal else None
        theirs = agreement.team_value
        if mine is None:
            status = "unknown"
        elif not mine or not theirs:
            status = "undecided"
        else:
            status = "same" if mine == theirs else "different"
        axes.append({"axis": agreement.axis, "label": labels.get(agreement.axis) or domain.axis(agreement.axis).description,
                     "personal_value": mine, "team_value": theirs, "status": status,
                     "team_agreed": agreement.agreed, "team_tied": agreement.tied, "team_votes": agreement.votes})
    # 본문 차이에서는 고정된 개인/팀 역할·출처 설명만 맞춘다. 실제 재사용에는 위 팀 원문을 쓴다.
    comparison_prompt = build_final_prompt(domain, basis["combo"], language=None if language == "ko" else language)
    return {"preference_id": item["id"], "revision": item["revision"], "team_code": code, "team_name": name,
            "domain_key": domain.name, "team_members": len(members), "personal_recognized": personal is not None,
            "axes": axes, "team_prompt": basis["prompt"], "team_snapshot": basis["snapshot"],
            "comparison_prompt": comparison_prompt, "team_language": language, "languages": languages}
