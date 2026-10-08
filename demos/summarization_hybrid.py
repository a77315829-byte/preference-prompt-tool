"""심화 요약의 API 없는 예시: 구체성 축을 원문에 있는 사실로 표현한다."""

from __future__ import annotations

import re

from demos.summarization import _sentence_limit, _sentences, generate_demo as base_demo


def _detail_score(sentence: str) -> int:
    """숫자와 문장 첫 단어 이외의 대문자 단어를 우선한다."""
    words = re.findall(r"\b[A-Za-z][A-Za-z'-]*\b", sentence)
    names = sum(word[0].isupper() for word in words[1:])
    if words and words[0] not in {"A", "An", "The", "This", "That"}:
        names += int(words[0][0].isupper())
    numbers = len(re.findall(r"\b\d+(?:[.,]\d+)*\b", sentence))
    return numbers * 2 + names


def generate_demo(source_text: str, combo: dict[str, str]) -> str:
    if combo.get("specificity") != "high":
        return base_demo(source_text, combo)

    sentences = _sentences(source_text)
    if not sentences:
        return base_demo(source_text, combo)

    count = _sentence_limit(combo.get("length", "normal"))
    topic = combo.get("topic", "").strip().lower()
    ranked = sorted(
        range(len(sentences)),
        key=lambda index: (
            -int(bool(topic) and topic in sentences[index].lower()),
            -_detail_score(sentences[index]),
            index,
        ),
    )
    selected = [sentences[index] for index in sorted(ranked[:count])]
    if combo.get("extractiveness") == "high":
        return "\n\n".join(f"Key point {index + 1}: {line}" for index, line in enumerate(selected))
    if combo.get("extractiveness") == "normal":
        overview = base_demo(source_text, {**combo, "extractiveness": "normal"})
        overview_sentences = set(sentences[:count])
        extra = next((sentences[index] for index in ranked if sentences[index] not in overview_sentences), None)
        return "\n\n".join([overview, f"Specific detail: {extra}"]) if extra else overview
    return "\n\n".join(selected)
