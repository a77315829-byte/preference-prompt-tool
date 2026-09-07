"""도메인: 문서 요약. 축별 검사 함수.

engine/metric_builder.py 가 domains/summarization.yaml 의 check.fn 이름으로
이 모듈에서 함수를 동적으로 찾아 호출한다. 각 함수는 (score, feedback)
튜플을 반환한다 - feedback은 GEPA 성찰에 쓰이는 자연어 피드백이다.

시그니처: fn(output, source, value, target) -> (score: float, feedback: str)
"""

from __future__ import annotations

import re


def _sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s]


def _words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9']+", text.lower())


def _bigrams(words: list[str]) -> set[tuple[str, str]]:
    return set(zip(words, words[1:]))


def sentence_count(output: str, source: str, value: str, target: dict) -> tuple[float, str]:
    n = len(_sentences(output))
    min_s = target.get("min_sentences")
    max_s = target.get("max_sentences")

    if min_s is not None and n < min_s:
        gap = min_s - n
        return max(0.0, 1.0 - 0.3 * gap), f"길이 위반: {n}문장 (목표 {min_s}문장 이상)."
    if max_s is not None and n > max_s:
        gap = n - max_s
        return max(0.0, 1.0 - 0.3 * gap), f"길이 위반: {n}문장 (목표 {max_s}문장 이하)."
    return 1.0, f"길이 충족: {n}문장."


def lexical_overlap(output: str, source: str, value: str, target: dict) -> tuple[float, str]:
    output_bigrams = _bigrams(_words(output))
    source_bigrams = _bigrams(_words(source))
    overlap = len(output_bigrams & source_bigrams) / len(output_bigrams) if output_bigrams else 0.0

    min_o = target.get("min_overlap")
    max_o = target.get("max_overlap")

    if min_o is not None and overlap < min_o:
        return max(0.0, overlap / min_o), (
            f"추출성 위반: 원문과의 표현 겹침 {overlap:.0%} (목표 {min_o:.0%} 이상). "
            "원문 표현을 더 그대로 사용하라."
        )
    if max_o is not None and overlap > max_o:
        excess = overlap - max_o
        return max(0.0, 1.0 - 2 * excess), (
            f"추출성 위반: 원문과의 표현 겹침 {overlap:.0%} (목표 {max_o:.0%} 이하). "
            "표현을 더 바꿔 써라."
        )
    return 1.0, f"추출성 충족: 원문과의 표현 겹침 {overlap:.0%}."


def keyword_presence(output: str, source: str, value: str, target: dict) -> tuple[float, str]:
    if not value:
        return 1.0, "주제 축 비활성 (해당 없음)."
    if value.lower() in output.lower():
        return 1.0, f"주제 충족: '{value}' 언급됨."
    return 0.0, f"주제 위반: '{value}'가 요약에 없음."
