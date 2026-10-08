"""도메인: 문서 요약 v2. 길이를 문장 수 대신 원문 대비 단어 비율로 잰다.

근거: experiments/length_ratio_labels.py (판단 기준은 실행 전에
docs/length_v2_preregistration.md 로 커밋). train 에서 정한 임계값으로 test 를
쟀을 때 MACSum 길이 라벨 균형정확도가 문장 수 0.494 -> 비율 0.710, topic 이
없는 요약에서는 0.979 였다. topic 이 있으면 요약 대상이 원문 일부라 분모를
모르므로 0.413 으로 문장 수보다 못하다 - 이 검사는 topic 없는 요약용이다.

나머지 축의 검사 함수는 v1 과 같다. domains/summarization_v2.yaml 이 extends 로
그 축들을 상속하므로 같은 이름이 이 모듈에도 있어야 한다.
"""

from __future__ import annotations

from checks.summarization import _words, keyword_presence, lexical_overlap, sentence_count  # noqa: F401


def length_ratio(output: str, source: str, value: str, target: dict) -> tuple[float, str]:
    """요약 단어 수 / 원문 단어 수. 피드백에는 이 원문에서의 목표 단어 수를
    같이 적는다 - 비율만 말하면 모델이 스스로 환산하지 못한다."""
    source_words = max(len(_words(source)), 1)
    words = len(_words(output))
    ratio = words / source_words
    min_r = target.get("min_ratio")
    max_r = target.get("max_ratio")

    def goal() -> str:
        low = f"{round(min_r * source_words)}" if min_r is not None else ""
        high = f"{round(max_r * source_words)}" if max_r is not None else ""
        if low and high:
            return f"{low}~{high}단어"
        return f"{low}단어 이상" if low else f"{high}단어 이하"

    if min_r is not None and ratio < min_r:
        return max(0.0, ratio / min_r), (
            f"길이 위반: {words}단어 (원문의 {ratio:.1%}). 이 원문에서는 {goal()}가 목표다. 더 길게 써라."
        )
    if max_r is not None and ratio > max_r:
        return max(0.0, 1.0 - (ratio - max_r) / max_r), (
            f"길이 위반: {words}단어 (원문의 {ratio:.1%}). 이 원문에서는 {goal()}가 목표다. 더 짧게 써라."
        )
    return 1.0, f"길이 충족: {words}단어 (원문의 {ratio:.1%})."
