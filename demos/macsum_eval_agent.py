"""문서 다듬기 실험실의 원문 기반, 결정적 데모 예시 생성기.

언어 모델 없이 사실을 추가하지 않는 범위에서 분량·문장 구조·강조점을
보여준다. 실제 편집 품질이나 축 판정 정확도를 보증하는 생성기는 아니다.
"""

from __future__ import annotations

import re


_LIMITS = {"concise": 1, "moderate": 2, "detailed": 6}


def _sentences(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text.strip())
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", normalized) if part.strip()]


def _entity_score(sentence: str) -> int:
    words = re.findall(r"\b[A-Za-z][A-Za-z'-]*\b", sentence)
    return sum(word[0].isupper() for word in words[1:]) + len(re.findall(r"\b\d+\b", sentence))


def _simple(sentence: str) -> str:
    # 접속된 두 독립절만 분리한다. 임의의 쉼표에서 나누면 문장이 깨진다.
    sentence = re.sub(r", (and|but) (?=[A-Z][a-z]+\s)", ". ", sentence)
    return re.sub(
        r" because ((?:[a-z]+\s+){2,}[a-z]+[.!?])$",
        lambda match: ". " + match.group(1)[0].upper() + match.group(1)[1:],
        sentence,
    )


def _formal(sentence: str) -> str:
    replacements = {"don't": "do not", "doesn't": "does not", "hasn't": "has not", "haven't": "have not", "can't": "cannot", "won't": "will not", "it's": "it is"}
    for short, full in replacements.items():
        sentence = re.sub(
            rf"(?<!\w){re.escape(short)}(?!\w)",
            lambda match: full.capitalize() if match.group()[0].isupper() else full,
            sentence,
            flags=re.IGNORECASE,
        )
    return sentence


def generate_demo(source_text: str, combo: dict[str, str]) -> str:
    sentences = _sentences(source_text)
    if not sentences:
        return "No source text was provided."

    limit = _LIMITS.get(combo.get("conciseness", "moderate"), 2)
    focus = combo.get("focus_on_entities")
    if focus == "entity-focused":
        ranked = sorted(range(len(sentences)), key=lambda index: (-_entity_score(sentences[index]), index))
        chosen = sorted(ranked[:limit])
        lines = [sentences[index] for index in chosen]
    elif focus == "mixed" and len(sentences) > 1:
        ranked = sorted(range(len(sentences)), key=lambda index: (-_entity_score(sentences[index]), index))
        entity_index = ranked[0]
        # 가장 짧은 예시도 일반 내용과 고유명사 내용을 함께 보여줘야
        # '일반' 또는 '리소스 중심' 중 하나와 똑같아지지 않는다.
        chosen = [entity_index, *[index for index in range(len(sentences)) if index != entity_index][:max(1, limit - 1)]]
        lines = [sentences[index] for index in chosen]
    else:
        lines = sentences[:limit]

    if combo.get("formality") == "formal":
        lines = [_formal(line) for line in lines]
    if combo.get("sentence_complexity") == "simple":
        lines = [_simple(line) for line in lines]
    elif combo.get("sentence_complexity") == "complex":
        if len(lines) > 1:
            lines = ["; ".join(line.rstrip(".!?") for line in lines) + "."]
        else:
            lines = [re.sub(r"\bbecause\b", "owing to the fact that", lines[0], count=1, flags=re.IGNORECASE)]

    separator = "\n\n" if combo.get("formality") == "informal" else " "
    result = separator.join(lines)
    return f"Quick update: {result}" if combo.get("formality") == "informal" else result
