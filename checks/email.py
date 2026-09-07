"""도메인: 이메일 초안 (11주차 확장성 검증용 더미 도메인). 축별 검사 함수.

engine/metric_builder.py 가 domains/email.yaml 의 check.fn 이름으로 이
모듈에서 함수를 동적으로 찾아 호출한다. 시그니처는 checks/summarization.py와
동일: fn(output, source, value, target) -> (score: float, feedback: str)
"""

from __future__ import annotations

import re

_CONTRACTIONS = re.compile(r"\b\w+'(m|re|s|ve|ll|d|t)\b", re.IGNORECASE)
_BULLET_LINE = re.compile(r"^\s*([-*•]|\d+[.)])\s+", re.MULTILINE)


def _sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s]


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


def contraction_ratio(output: str, source: str, value: str, target: dict) -> tuple[float, str]:
    sentences = _sentences(output)
    if not sentences:
        return 0.0, "격식 판단 불가: 문장 없음."
    ratio = sum(1 for s in sentences if _CONTRACTIONS.search(s)) / len(sentences)

    min_r = target.get("min_ratio")
    max_r = target.get("max_ratio")

    if min_r is not None and ratio < min_r:
        return max(0.0, ratio / min_r), f"격식 위반: 축약형 비율 {ratio:.0%} (목표 {min_r:.0%} 이상). 더 캐주얼하게 써라."
    if max_r is not None and ratio > max_r:
        excess = ratio - max_r
        return max(0.0, 1.0 - 2 * excess), f"격식 위반: 축약형 비율 {ratio:.0%} (목표 {max_r:.0%} 이하). 축약형을 풀어써라."
    return 1.0, f"격식 충족: 축약형 비율 {ratio:.0%}."


def bullet_ratio(output: str, source: str, value: str, target: dict) -> tuple[float, str]:
    lines = [ln for ln in output.splitlines() if ln.strip()]
    if not lines:
        return 0.0, "구조 판단 불가: 내용 없음."
    ratio = len(_BULLET_LINE.findall(output)) / len(lines)

    min_r = target.get("min_ratio")
    max_r = target.get("max_ratio")

    if min_r is not None and ratio < min_r:
        return max(0.0, ratio / min_r), f"구조 위반: 글머리기호 비율 {ratio:.0%} (목표 {min_r:.0%} 이상). 목록으로 정리하라."
    if max_r is not None and ratio > max_r:
        return 0.0, f"구조 위반: 글머리기호 비율 {ratio:.0%} (목표 {max_r:.0%} 이하). 산문으로 풀어써라."
    return 1.0, f"구조 충족: 글머리기호 비율 {ratio:.0%}."
