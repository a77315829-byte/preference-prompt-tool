"""Explicit source priorities and deterministic conflict handling, without model calls.

Checks sentence-count feasibility for selected complete verbatim sentences only.
It neither infers important facts nor certifies semantic compressibility.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

import yaml

from checks.summarization_grounded_v3 import normalize, split_sentences, strip_publisher
from engine.domain_loader import load_domain
from engine.generator import build_final_prompt

ROOT = Path(__file__).resolve().parent
DOMAIN_PATHS = {
    "summarization": ROOT / "domains/summarization_grounded_v3.yaml",
    "summarization_ko": ROOT / "domains/summarization_ko_grounded_v3.yaml",
}
MAX_SOURCE = 12_000
MAX_REQUIRED = 8
RESOLUTIONS = ("expand", "rephrase", "keep_limits")


@lru_cache(maxsize=1)
def _copy():
    return yaml.safe_load((ROOT / "domains/summary_contract.yaml").read_text(encoding="utf-8"))


def _profile(value):
    if not isinstance(value, dict):
        raise ValueError("분량과 원문 표현 방식을 직접 확인해 주세요.")
    if set(value) - {"length", "extractiveness", "topic"}:
        raise ValueError("지원하지 않는 요약 조건입니다.")
    if value.get("length") not in ("short", "normal", "long"):
        raise ValueError("분량을 선택해 주세요.")
    if value.get("extractiveness") not in ("normal", "high", "fully"):
        raise ValueError("원문 표현 방식을 선택해 주세요.")
    topic = value.get("topic", "")
    if not isinstance(topic, str) or len(topic) > 300:
        raise ValueError("요약 초점은 300자 이내의 글로 입력해 주세요.")
    return {"length": value["length"], "extractiveness": value["extractiveness"], "topic": topic.strip()}


def source_sentences(source):
    """Displayable unique complete sentence candidates, in source order."""
    return list(dict.fromkeys(s for s in split_sentences(strip_publisher(source))
                             if re.search(r"[.!?。][\"'”’\)\]]*$", s)))


def build_contract_prompt(domain_key, effective_profile, resolution="preserve", language="en"):
    """Reusable instructions contain no source text or selected passages."""
    if not isinstance(domain_key, str) or domain_key not in DOMAIN_PATHS or language not in ("en", "ko"):
        raise ValueError("지원하지 않는 요약 도메인 또는 지침 언어입니다.")
    if resolution not in ("preserve", *RESOLUTIONS):
        raise ValueError("지원하지 않는 조건 처리 방식입니다.")
    profile = _profile(effective_profile)
    domain = load_domain(DOMAIN_PATHS[domain_key])
    # Korean is the source template; English is the explicit translation.
    base = build_final_prompt(domain, profile, language=None if language == "ko" else language)
    copy = _copy()[language]
    rules = "\n".join(f"- {r}" for r in copy["rules"])
    return f"{base}\n\n{copy['heading']}\n{rules}\n- {copy['policies'][resolution]}"


def task_data_block(source, required_sentences, resolution, language="en"):
    """Shared task input used for all benchmark arms as well as the product."""
    copy = _copy()[language]
    data = {"coverage_policy": "prioritize_with_omission" if resolution == "keep_limits" else "all_required",
            "required_passages": required_sentences, "source": source}
    return f"{copy['task_heading']}\n{copy['task_instruction']}\n" + json.dumps(data, ensure_ascii=False, indent=2)


def prepare_summary_contract(body):
    if not isinstance(body, dict):
        raise ValueError("요약 조건 요청은 객체여야 합니다.")
    domain_key = body.get("domainKey")
    if not isinstance(domain_key, str) or domain_key not in DOMAIN_PATHS:
        raise ValueError("영어 또는 한국어 문서 요약에서 사용할 수 있습니다.")
    original = _profile(body.get("profile"))
    source = body.get("sourceText")
    if not isinstance(source, str) or not source.strip() or len(source) > MAX_SOURCE:
        raise ValueError("원문은 1~12,000자로 입력해 주세요. 넘친 내용을 자동으로 자르지 않습니다.")
    source = source.strip()
    available = source_sentences(source)
    selected = body.get("requiredSentences", [])
    if not isinstance(selected, list) or len(selected) > MAX_REQUIRED or any(not isinstance(s, str) for s in selected):
        raise ValueError("고른 원문 문장은 최대 8개여야 합니다.")
    selected = [normalize(s) for s in selected]
    if len(set(selected)) != len(selected):
        raise ValueError("같은 원문 문장을 중복 선택할 수 없습니다.")
    if any(s not in available for s in selected):
        raise ValueError("고른 문장이 현재 원문의 완전한 문장과 일치하지 않습니다. 원문 변경 후 다시 골라 주세요.")
    # Canonical source order: a UI checkbox click order must not silently change priority.
    selected = [s for s in available if s in set(selected)]
    resolution = body.get("resolution")
    if resolution is not None and resolution not in RESOLUTIONS:
        raise ValueError("조건 충돌 처리 방식을 다시 선택해 주세요.")
    domain = load_domain(DOMAIN_PATHS[domain_key])
    limit = domain.axis("length").check_for(original["length"]).target.get("max_sentences")
    collision = original["extractiveness"] == "fully" and limit is not None and len(selected) > limit
    conflict = ({"required_sentences": len(selected), "max_sentences": limit,
                 "message": f"고른 서로 다른 원문 {len(selected)}문장을 그대로 모두 남기면 최대 {limit}문장 조건을 지킬 수 없습니다."}
                if collision else None)
    if resolution is not None and not collision:
        raise ValueError("현재 조건에는 이 분량·발췌 충돌이 없습니다. 처리 방식을 초기화하고 다시 확인해 주세요.")
    notices = ["문장 구분 규칙으로 확인한 결과입니다. 중요도·사실성·의미상 압축 가능 여부를 자동 검증한 것은 아닙니다.",
               "고른 문장에 대명사·인용이 있으면 추가 맥락이 필요할 수 있습니다. 문장 수가 맞아도 내용 보존을 보장하지 않습니다."]
    result = {"version": 1, "status": "needs_resolution" if collision and resolution is None else "ready",
              "available_sentences": available, "required_sentences": selected,
              "original_profile": original, "effective_profile": dict(original), "conflict": conflict,
              "resolution": resolution or "preserve", "notices": notices, "prompts": {}, "task_requests": {}}
    if result["status"] == "needs_resolution":
        return result
    effective = result["effective_profile"]
    if resolution == "expand":
        effective["length"] = "normal" if len(selected) <= 4 else "long"
        notices.append("고른 문장을 모두 담을 수 있도록 분량만 늘렸습니다. 맥락에 따라 추가 확인이 필요합니다.")
    elif resolution == "rephrase":
        effective["extractiveness"] = "normal"
        notices.append("길이는 유지하고 재서술을 허용했습니다. 모든 정보가 들어갈 수 있는지는 요약 결과에서 확인해야 합니다.")
    elif resolution == "keep_limits":
        notices.append("분량·발췌 조건을 유지하며 고른 정보 중 일부 생략을 허용했습니다. 전체 보존으로 표시하지 않습니다.")
    elif selected and original["extractiveness"] != "fully":
        notices.append("재서술의 의미상 압축 가능 여부는 이 규칙으로 판별할 수 없습니다. 필요하면 분량을 조정해 주세요.")
    notices.append("원문과 고른 문장은 이번 작업용 복사에만 포함됩니다. 다른 원문에는 조건을 다시 확인해 주세요.")
    for language in ("en", "ko"):
        prompt = build_contract_prompt(domain_key, effective, result["resolution"], language)
        result["prompts"][language] = prompt
        result["task_requests"][language] = prompt + "\n\n" + task_data_block(source, selected, result["resolution"], language)
    return result
