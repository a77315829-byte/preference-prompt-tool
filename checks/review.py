"""도메인: 고객 리뷰 작성. 축별 검사 함수.

engine/metric_builder.py 가 domains/review.yaml 의 check.fn 이름으로 이
모듈에서 함수를 동적으로 찾아 호출한다. 시그니처는 다른 도메인과 동일:
fn(output, source, value, target) -> (score: float, feedback: str)

sentiment 축의 어휘 사전과 임계값은 실제 Yelp 리뷰 3,000건(별점 기반
라벨)으로 검증했다 (experiments/review_dataset.py) - negative 평균
-0.0022, neutral 0.019, positive 0.0392로 단조 증가함을 확인한 뒤 중앙값
사이 중점으로 임계값을 잡았다. specificity 축(6주차)의 교훈: 정성적으로
그럴듯해 보이는 어휘 목록도 실측 없이는 못 믿는다.
"""

from __future__ import annotations

import re

_POS_WORDS = {
    "great", "excellent", "amazing", "love", "loved", "best", "wonderful",
    "fantastic", "perfect", "delicious", "friendly", "awesome", "good",
    "recommend", "favorite", "happy", "nice", "enjoyed", "fresh", "clean",
}
_NEG_WORDS = {
    "bad", "terrible", "horrible", "worst", "awful", "disappointing", "rude",
    "poor", "never", "waste", "disgusting", "slow", "cold", "dirty",
    "overpriced", "mediocre", "bland", "wrong", "sucks",
}


def _sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s]


def _sentiment_score(text: str) -> float:
    words = re.findall(r"[a-z]+", text.lower())
    if not words:
        return 0.0
    pos = sum(1 for w in words if w in _POS_WORDS)
    neg = sum(1 for w in words if w in _NEG_WORDS)
    return (pos - neg) / len(words)


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


def sentiment(output: str, source: str, value: str, target: dict) -> tuple[float, str]:
    s = _sentiment_score(output)
    min_s = target.get("min_score")
    max_s = target.get("max_score")

    if min_s is not None and s < min_s:
        return max(0.0, s / min_s if min_s else 0.0), (
            f"어조 위반: 감성 점수 {s:.4f} (목표 {min_s:.4f} 이상). 더 긍정적으로 써라."
        )
    if max_s is not None and s > max_s:
        excess = s - max_s
        return max(0.0, 1.0 - 20 * excess), (
            f"어조 위반: 감성 점수 {s:.4f} (목표 {max_s:.4f} 이하). 더 부정적/중립적으로 써라."
        )
    return 1.0, f"어조 충족: 감성 점수 {s:.4f}."


def keyword_presence(output: str, source: str, value: str, target: dict) -> tuple[float, str]:
    if not value:
        return 1.0, "주제 축 비활성 (해당 없음)."
    if value.lower() in output.lower():
        return 1.0, f"주제 충족: '{value}' 언급됨."
    return 0.0, f"주제 위반: '{value}'가 리뷰에 없음."
