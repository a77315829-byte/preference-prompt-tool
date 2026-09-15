"""문서 요약 (한국어) 도메인의 규칙 기반 데모 생성기.

engine/demo_generator.py 가 도메인 이름(summarization_ko)으로 이 모듈을
찾아 generate_demo(source_text, combo) 를 호출한다. API 키 없이 전체
흐름을 시험하는 용도이므로 LLM을 쓰지 않는다.

demos/summarization.py(영어)와 다른 점: 영어 쪽은 extractiveness=normal
일 때 키워드를 나열하는데, 한국어에서는 그게 요약으로 안 읽힌다. 대신
원문 문장의 서술어를 명사형으로 바꿔 개조식으로 압축한다 - 실제
한국어 요약에서 흔히 쓰는 문체이고, 원문 발췌와 눈에 띄게 달라서
A/B 비교 데모로 쓸 만하다.

주의: 데모 모드는 checks/ 를 거치지 않는다(GEPA 최적화는 API 모드에서만
동작한다). 따라서 여기서 만든 결과물의 실측 추출성 값이 축 라벨과
정확히 일치할 필요는 없다 - 사용자가 문체 차이를 구분할 수 있으면 된다.
"""

from __future__ import annotations

import re

_SENT_SPLIT_RE = re.compile(r"(?<=[.!?。])\s+")

# 축 값별 목표 문장 수. domains/summarization_ko.yaml 의 length 임계값과
# 맞춘다 (short: 2 이하, normal: 3~4, long: 5 이상).
_SENTENCE_LIMITS = {"short": 2, "normal": 4, "long": 5}

# 서술어 -> 명사형 개조식 변환. 어미를 떼면 그대로 명사가 되는 한자어
# 서술어(발표했다 -> 발표, 공급된다 -> 공급)만 다룬다. 목록에 없으면
# 문장을 그대로 두므로 비문이 생기지 않는다.
_PREDICATE_ENDINGS = (
    "하였습니다", "되었습니다", "했습니다", "됐습니다",
    "하였다", "되었다", "합니다", "됩니다",
    "했다", "됐다", "한다", "된다",
)

_COPULA_ENDINGS = ("이라고 밝혔다", "라고 밝혔다", "이라고 말했다", "라고 말했다")


def _sentences(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text.strip())
    if not normalized:
        return []
    return [part.strip() for part in _SENT_SPLIT_RE.split(normalized) if part.strip()]


def _strip_final_punctuation(sentence: str) -> str:
    return sentence.rstrip(".!?。 ")


def _to_nominal(sentence: str) -> str:
    """문장의 서술어를 명사형으로 바꿔 개조식 한 줄로 만든다.

    변환할 수 없으면 원문 문장을 그대로 돌려준다 (비문 방지).
    """
    body = _strip_final_punctuation(sentence)

    for ending in _COPULA_ENDINGS:
        if body.endswith(ending):
            return body[: -len(ending)].strip() + " (발언)"

    words = body.split()
    if not words:
        return body

    last = words[-1]
    for ending in _PREDICATE_ENDINGS:
        if last.endswith(ending):
            stem = last[: -len(ending)]
            if len(stem) >= 2:
                return " ".join(words[:-1] + [stem]).strip()
            # 서술어가 어미뿐인 경우("했다") 그 어절을 버린다.
            if len(words) > 1:
                return " ".join(words[:-1]).strip()
    return body


def _ensure_period(text: str) -> str:
    return text if text.endswith((".", "!", "?")) else f"{text}."


def _extracted(sentences: list[str], count: int) -> list[str]:
    if not sentences:
        return ["원문이 입력되지 않았습니다."]
    return sentences[:count]


def generate_demo(source_text: str, combo: dict[str, str]) -> str:
    sentences = _sentences(source_text)
    count = _SENTENCE_LIMITS.get(combo.get("length", "normal"), 4)
    extractiveness = combo.get("extractiveness", "normal")

    selected = _extracted(sentences, count)

    if extractiveness == "normal":
        # 개조식으로 압축 - 원문 문장을 그대로 쓰지 않는다.
        lines = [f"- {_to_nominal(sentence)}" for sentence in selected]
        return "\n".join(lines)

    if extractiveness == "high":
        lines = [
            f"핵심 {index + 1}. {_ensure_period(sentence)}"
            for index, sentence in enumerate(selected)
        ]
        return "\n\n".join(lines)

    # fully - 원문 문장을 손대지 않고 그대로 이어붙인다.
    return " ".join(_ensure_period(sentence) for sentence in selected)
