"""문서 요약 도메인의 규칙 기반 데모 생성기."""

from __future__ import annotations

import re
from collections import Counter


_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "but", "by",
    "for", "from", "had", "has", "have", "he", "her", "his", "in",
    "is", "it", "its", "of", "on", "or", "she", "that", "the", "their",
    "they", "this", "to", "was", "were", "will", "with",
}


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


def _keywords(text: str, limit: int = 12) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z'-]{2,}", text.lower())
    counts = Counter(word for word in words if word not in _STOPWORDS)
    return [word for word, _ in counts.most_common(limit)]


def _abstract_summary(source_text: str, count: int) -> list[str]:
    words = _keywords(source_text, limit=max(6, count * 3))
    if not words:
        return ["The source presents its main subject and supporting details."]

    chunks = [words[i::count] for i in range(count)]
    labels = (
        "Main focus", "Key context", "Notable detail", "Related point",
        "Further context", "Overall theme",
    )
    return [
        f"{labels[index % len(labels)]}: {', '.join(chunk[:3])}."
        for index, chunk in enumerate(chunks)
        if chunk
    ]


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
