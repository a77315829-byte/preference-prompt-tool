"""Product-only conflict handling; frozen v1 prompts and experiments stay intact."""
from functools import lru_cache

import yaml

import summary_contracts as legacy
from engine.domain_loader import load_domain
from engine.generator import build_final_prompt
from summary_input_policy import input_policy, validate_summary_source


@lru_cache(maxsize=1)
def _copy():
    return yaml.safe_load((legacy.ROOT / "domains/summary_contract/v2.yaml").read_text(encoding="utf-8"))


def _bounds(domain, length):
    target = domain.axis("length").check_for(length).target
    return {"min_sentences": target.get("min_sentences", 1),
            "max_sentences": target.get("max_sentences")}


def build_contract_prompt(domain_key, profile, resolution, language):
    domain = load_domain(legacy.DOMAIN_PATHS[domain_key])
    base = build_final_prompt(domain, profile, language=None if language == "ko" else language)
    copy = legacy._copy()[language]
    extra = _copy()[language]
    rules = "\n".join(f"- {rule}" for rule in [*copy["rules"], extra["extraction_rule"]])
    policy = extra["shorten"] if resolution == "shorten" else copy["policies"][resolution]
    return f"{base}\n\n{copy['heading']}\n{rules}\n- {policy}"


def prepare_summary_contract(body):
    if not isinstance(body, dict):
        raise ValueError("요약 조건 요청은 객체여야 합니다.")
    # Apply exactly the same raw-input counting policy as the session endpoint.
    source = validate_summary_source(body.get("sourceText"))
    resolution = body.get("resolution")
    if resolution is not None and resolution not in (*legacy.RESOLUTIONS, "shorten"):
        raise ValueError("조건 충돌 처리 방식을 다시 선택해 주세요.")
    # Reuse v1's strict domain/profile/passage validation without changing its bytes.
    result = legacy.prepare_summary_contract({**body, "resolution": None})
    original = result["original_profile"]
    domain_key = body["domainKey"]
    domain = load_domain(legacy.DOMAIN_PATHS[domain_key])
    bounds = _bounds(domain, original["length"])
    available = len(result["available_sentences"])
    selected = len(result["required_sentences"])
    conflict = result["conflict"]
    choices = []
    if conflict:
        conflict = {**conflict, "kind": "required_over_budget"}
        choices = ["expand", "rephrase", "keep_limits"]
    elif original["extractiveness"] == "fully" and available < bounds["min_sentences"]:
        conflict = {"kind": "source_under_minimum", "available_sentences": available,
                    "min_sentences": bounds["min_sentences"],
                    "message": f"발췌할 수 있는 서로 다른 완전한 원문 문장은 {available}개인데, 선택한 분량은 최소 {bounds['min_sentences']}문장입니다. 반복이나 새 문장 추가 없이 두 조건을 지킬 수 없습니다."}
        choices = (["shorten"] if available else []) + ["rephrase"]
    if resolution is not None and resolution not in choices:
        raise ValueError("현재 충돌에 맞는 처리 방식을 다시 선택해 주세요. 원문이나 조건이 바뀌면 이전 선택을 적용하지 않습니다.")
    result.update(version=2, input_policy=input_policy(), length_limits=bounds,
                  available_resolutions=choices, conflict=conflict,
                  resolution=resolution or "preserve", coverage_policy="all_required",
                  status="needs_resolution" if conflict and resolution is None else "ready",
                  prompts={}, task_requests={})
    if result["status"] == "needs_resolution":
        if not available:
            result["notices"].append("완전한 문장으로 구분되지 않은 원문은 직접 보완하거나 재서술을 허용해 주세요. 문장을 자동으로 만들지 않습니다.")
        return result
    effective = result["effective_profile"]
    if resolution in ("expand", "shorten"):
        feasible = [value.value for value in domain.axis("length").values
                    if _bounds(domain, value.value)["min_sentences"] <= available
                    and (_bounds(domain, value.value)["max_sentences"] is None
                         or selected <= _bounds(domain, value.value)["max_sentences"])]
        if not feasible:
            raise ValueError("원문과 보존 문장을 담을 수 있는 분량이 없습니다. 조건을 다시 확인해 주세요.")
        effective["length"] = (min if resolution == "expand" else max)(
            feasible, key=lambda length: _bounds(domain, length)["min_sentences"])
        result["notices"].append("분량만 조정했습니다. 완전 발췌와 고른 모든 문장의 보존 요청은 유지합니다.")
    elif resolution == "rephrase":
        effective["extractiveness"] = "normal"
        result["notices"].append("길이는 유지하고 재서술을 허용했습니다. 의미상 압축·분량 충족과 내용 보존은 실제 요약에서 확인해야 합니다.")
    elif resolution == "keep_limits":
        result["coverage_policy"] = "prioritize_with_omission"
        result["notices"].append("분량·발췌 조건을 유지하고 선택한 내용 중 일부 생략을 허용했습니다. 전체 보존을 요청한 결과가 아닙니다.")
    result["length_limits"] = _bounds(domain, effective["length"])
    for language in ("en", "ko"):
        prompt = build_contract_prompt(domain_key, effective, result["resolution"], language)
        result["prompts"][language] = prompt
        result["task_requests"][language] = prompt + "\n\n" + legacy.task_data_block(
            source, result["required_sentences"], result["resolution"], language)
    return result
