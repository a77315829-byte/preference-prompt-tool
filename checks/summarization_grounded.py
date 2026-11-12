"""Versioned summary form checks; content coverage/factuality need separate review.

Sentence boundaries are a conservative punctuation heuristic, not a linguistic
parser. The original research checks remain unchanged for reproducibility.
"""
from __future__ import annotations

import re

from checks.summarization import keyword_presence

_PUBLISHER = re.compile(r"^\s*\((CNN|The Hollywood Reporter)\)\s*", re.IGNORECASE)
_ABBREVIATION = re.compile(
    r"\b(?:Mr|Mrs|Ms|Dr|Prof|Sr|Jr|St|Co|Inc|Ltd|vs|etc)\.", re.IGNORECASE
)
_ACRONYM = re.compile(r"\b(?:[A-Za-z]\.){2,}")
_INITIAL = re.compile(r"\b[A-Z]\.(?=\s+[A-Z][a-z])")
_NUMBER_LABEL = re.compile(r"\bNo\.(?=\s*\d)", re.IGNORECASE)
_BOUNDARY = re.compile(r"[.!?。]+[\"'”’\)\]]*(?=\s|$)")


def normalize(text: str) -> str:
    return " ".join(text.split())


def strip_publisher(text: str) -> str:
    """Only a known publisher tag at the start of the entire text is optional."""
    return _PUBLISHER.sub("", text, count=1)


def split_sentences(text: str) -> list[str]:
    """Handle common abbreviations/decimals and attached closing quotes.

    Unknown abbreviations and unusual dialogue can remain ambiguous. Keep the
    original text unchanged; the masked copy is only used to locate boundaries.
    """
    original = normalize(text)
    if not original:
        return []
    masked = original
    for pattern in (_ABBREVIATION, _ACRONYM, _INITIAL, _NUMBER_LABEL):
        masked = pattern.sub(lambda m: m.group().replace(".", "\u2024"), masked)
    masked = re.sub(r"(?<=\d)\.(?=\d)", "\u2024", masked)
    parts, start = [], 0
    for match in _BOUNDARY.finditer(masked):
        # A quote followed by a lowercase reporting clause remains one sentence.
        tail = masked[match.end():].lstrip()
        quoted = any(c in match.group() for c in '\"”’')
        if quoted and tail and tail[0].isascii() and tail[0].islower():
            continue
        parts.append(original[start:match.end()].strip())
        start = match.end()
    if original[start:].strip():
        parts.append(original[start:].strip())
    return [part for part in parts if part]


def sentence_count(output: str, source: str, value: str, target: dict) -> tuple[float, str]:
    count = len(split_sentences(output))
    if not count:
        return 0.0, "빈 요약이다."
    minimum, maximum = target.get("min_sentences"), target.get("max_sentences")
    if minimum is not None and count < minimum:
        return max(0.0, 1 - .3 * (minimum - count)), f"길이 위반: {count}문장, 최소 {minimum}문장."
    if maximum is not None and count > maximum:
        return max(0.0, 1 - .3 * (count - maximum)), f"길이 위반: {count}문장, 최대 {maximum}문장."
    return 1.0, f"문장 구분 휴리스틱 기준 길이 충족: {count}문장. 내용 보존은 별도 확인한다."


def lexical_overlap(output: str, source: str, value: str, target: dict) -> tuple[float, str]:
    """Surface overlap is a diagnostic proxy, never a factuality/meaning score."""
    if not output.strip():
        return 0.0, "빈 요약이다."
    if target.get("language") == "ko":
        from checks.summarization_ko import lexical_overlap as legacy_overlap
    else:
        from checks.summarization import lexical_overlap as legacy_overlap
    score, detail = legacy_overlap(output, source, value, target)
    return score, "표현 겹침 참고 지표(의미·사실성 판정 아님): " + detail


def verbatim_sentences(output: str, source: str, value: str, target: dict) -> tuple[float, str]:
    """Require complete original sentences, ignoring whitespace and leading tags.

    This tests textual extraction only. True source sentences may still omit
    essential context or reflect an incorrect source; no factuality claim follows.
    """
    output_tag, source_tag = _PUBLISHER.match(output), _PUBLISHER.match(source)
    if output_tag and (not source_tag or output_tag.group(1).casefold() != source_tag.group(1).casefold()):
        return 0.0, "완전 발췌 위반: 원문에 없는 매체 태그를 추가하거나 원문 매체 태그를 바꿨다."
    candidates = split_sentences(strip_publisher(output))
    originals = set(split_sentences(strip_publisher(source)))
    if not candidates or not originals:
        return 0.0, "빈 요약 또는 원문이다."
    valid = [sentence in originals and bool(re.search(r"[.!?。][\"'”’\)\]]*$", sentence))
             for sentence in candidates]
    if all(valid):
        return 1.0, "완전 발췌 형식 충족. 공백·문서 맨 앞의 지정 매체 태그만 정규화했다. 내용 보존은 별도 확인한다."
    return 0.0, f"완전 발췌 위반: {len(valid) - sum(valid)}개 문장이 원문 완전 문장과 다르거나 불완전하다."
