"""문서 요약 도메인의 규칙 기반 데모 생성기."""

from __future__ import annotations

import re


def _sentences(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text.strip())
    if not normalized:
        return []
    parts = re.split(r"(?<=[.!?])\s+", normalized)
    return [part.strip() for part in parts if part.strip()]


def _sentence_limit(length: str) -> int:
    return {"short": 2, "normal": 4, "long": 6}.get(length, 4)


def _ensure_period(text: str) -> str:
    return text if text.endswith((".", "!", "?")) else f"{text}."


def _abstract_summary(source_text: str, count: int) -> list[str]:
    # 규칙 기반 데모는 안전하게 바꿔 쓸 수 없는 내용을 추측하지 않는다.
    # 핵심 문장을 원문 그대로 가져오되, 읽기 쉬운 개요 형식으로 보여 준다.
    sentences = _selected_sentences(source_text, count)
    return [f"Summary: {_ensure_period(sentences[0])}", *sentences[1:]]


def _selected_sentences(source_text: str, count: int) -> list[str]:
    sentences = _sentences(source_text)
    return sentences[:count] if sentences else ["No source text was provided."]


def generate_demo(source_text: str, combo: dict[str, str]) -> str:
    count = _sentence_limit(combo.get("length", "normal"))
    extractiveness = combo.get("extractiveness", "normal")

    if extractiveness == "normal":
        lines = _abstract_summary(source_text, count)
    else:
        lines = _selected_sentences(source_text, count)
        if extractiveness == "high":
            lines = [f"Key point {index + 1}: {_ensure_period(line)}" for index, line in enumerate(lines)]

    return "\n\n".join(_ensure_period(line) for line in lines)
