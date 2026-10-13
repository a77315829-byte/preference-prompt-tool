"""전용 데모 생성기가 없는 도메인을 위한 기본 규칙 기반 생성기.

engine/demo_generator.py 는 먼저 `demos.<도메인명>` 을 찾고, 없으면 이
모듈로 내려온다. 덕분에 새 도메인은 domains/*.yaml 과 checks/*.py 만
추가하면 앱의 데모 모드까지 그대로 동작한다 - 전에는 도메인마다 데모
생성기를 손으로 써야 해서, "engine/ 은 안 고쳐도 되지만 데모 생성기는
짜야 한다"는 구멍이 확장성 주장에 남아 있었다.

**이 모듈은 도메인 특정 단어를 써도 된다.** 절대 규칙 1이 금지하는 것은
`engine/` 안이고, `demos/` 는 도메인을 아는 계층이다. 여기서는 여러
도메인이 공유하는 축 이름(length, formality, structure, sentiment)을
실제로 구현한다. 축을 흉내만 내고 아무렇게나 다른 텍스트를 내놓으면,
사용자의 선택이 축과 무관해져서 추정된 선호가 의미를 잃는다.

모르는 축은 조용히 무시하지 않고 적용된 지침을 화면에 적는다 - 데모가
무엇을 반영했는지 사용자가 확인할 수 있어야 한다.

현재 이 생성기로 도는 도메인: review(length·sentiment·topic),
email(length·formality·structure). 둘 다 결과물이 영어다.
"""

from __future__ import annotations

import re
from collections import Counter

# 축 값별 목표 문장 수. review.yaml·email.yaml 의 sentence_count 임계값과
# 맞춘다 (short: 2 이하, normal: 3~5, long: 6 이상).
_SENTENCE_LIMITS = {"short": 2, "normal": 4, "long": 6}

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "but", "by", "for",
    "from", "had", "has", "have", "he", "her", "his", "i", "in", "is", "it",
    "its", "me", "my", "of", "on", "or", "our", "she", "that", "the", "their",
    "them", "they", "this", "to", "was", "we", "were", "will", "with", "you",
    "your", "about", "would", "could", "should", "very", "really", "just",
}

# 어조별 문장 틀. sentiment 축이 없는 도메인은 neutral 을 쓴다.
#
# 키워드는 {k} 한 자리에만, 쉼표로 이어진 목록으로 넣는다. 전에는
# "The {k} was excellent" 처럼 명사 자리에 꽂았는데, 원문에서 뽑은 단어가
# 동사면("visited", "ask") 비문이 됐다. 품사 태거를 새로 들이지 않고
# 문법을 지키려면 어떤 단어가 와도 되는 자리에만 쓰는 게 맞다.
#
# 축약형은 모호하지 않은 것만 쓴다. "I'd" 는 would/had 양쪽이라
# formal 로 펼칠 때 시제가 틀어졌다("I would expected").
_TONE_TEMPLATES = {
    "positive": (
        "{source}.",
        "Overall, I found the experience excellent.",
        "These details left a good impression on me.",
        "For me, the positives mattered most.",
        "I came away feeling good about the visit.",
        "That is my view based on what I observed.",
    ),
    "neutral": (
        "{source}.",
        "Those are the main details of my experience.",
        "I can see both positive and negative aspects in them.",
        "My view is mixed rather than strongly one-sided.",
        "The details speak for themselves.",
        "That is my view based on what I observed.",
    ),
    "negative": (
        "{source}.",
        "Overall, I found the experience disappointing.",
        "The drawbacks weighed on my impression.",
        "For me, the negatives mattered most.",
        "I came away with reservations about the visit.",
        "That is my view based on what I observed.",
    ),
}

# sentiment 축이 없는 도메인은 의견문이 아니라 초안을 쓰는 과제일
# 가능성이 높다(이메일 초안 등). 위 문체를 그대로 쓰면 "Overall the
# experience was..." 처럼 리뷰 말투가 나온다. 축 구성을 문체 선택의
# 근거로 쓰는 휴리스틱이고, 도메인 이름에 의존하지 않는다.
_DRAFT_TEMPLATES = (
    "I'm writing to ask if you could {request}.",
    "Thanks for your help.",
    "Please let me know once you have an update.",
    "I look forward to your reply.",
    "Please get back to me when you can.",
    "Thank you for taking the time to review this request.",
)

# 격식 축(formality)용 축약형 펼치기. casual 은 위 틀의 축약형을 그대로
# 두고, formal 은 풀어쓴다. 위에서 모호한 축약형을 배제했으므로 단순
# 치환으로 안전하다.
_EXPANSIONS = (
    ("isn't", "is not"), ("didn't", "did not"), ("doesn't", "does not"),
    ("wouldn't", "would not"), ("don't", "do not"), ("can't", "cannot"),
    ("won't", "will not"), ("I'm", "I am"), ("I've", "I have"),
    ("it's", "it is"), ("that's", "that is"), ("there's", "there is"),
)

_FALLBACK_KEYWORDS = ("request", "detail", "point", "item", "update")


def _keywords(text: str, limit: int = 8) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z'-]{2,}", text.lower())
    counts = Counter(w for w in words if w not in _STOPWORDS)
    found = [w for w, _ in counts.most_common(limit)]
    return found or list(_FALLBACK_KEYWORDS)


def _templates(combo: dict[str, str], has_sentiment_axis: bool) -> tuple[str, ...]:
    """쓸 문장 틀을 고른다.

    어조 축이 있으면 그 값에 맞는 의견문 틀을, 없으면 초안 틀을 쓴다.
    """
    if not has_sentiment_axis:
        return _DRAFT_TEMPLATES
    value = combo.get("sentiment", "")
    return _TONE_TEMPLATES.get(value, _TONE_TEMPLATES["neutral"])


def _sentences(
    combo: dict[str, str], keywords: list[str], has_sentiment_axis: bool = True,
    source_text: str = "",
) -> list[str]:
    count = _SENTENCE_LIMITS.get(combo.get("length", "normal"), 4)
    templates = _templates(combo, has_sentiment_axis)
    highlight = ", ".join(keywords[:3])
    # 리뷰 메모의 실제 내용을 먼저 담는다. 어조는 주관적인 평가 문장에만
    # 반영하고, 원문에 없는 방문·추천·약속 위반 등의 사건은 만들어내지 않는다.
    source = re.sub(r"[.!?]+\s*", "; ", source_text.strip()).strip(" ;")
    source = source or "No specific details were provided"
    # 이메일처럼 sentiment 축이 없는 초안 과제에서는 키워드 나열 대신
    # 원문 요청을 사용한다. 첫 두 문장에도 축약형을 두어 짧은 격식 A/B가
    # 동일한 카드로 렌더링되지 않게 한다.
    request = re.sub(r"^Ask\s+.+?\s+to\s+", "", source_text.strip(), flags=re.I)
    request = request.rstrip(".!? ") or "share the details of your request"
    return [
        templates[i % len(templates)].format(k=highlight, request=request, source=source)
        for i in range(count)
    ]


def _apply_formality(lines: list[str], combo: dict[str, str]) -> list[str]:
    if combo.get("formality") != "formal":
        return lines
    formal = []
    for line in lines:
        for short, long in _EXPANSIONS:
            line = line.replace(short, long)
            line = line.replace(short.capitalize(), long.capitalize())
        formal.append(line)
    return formal


def _applied_notes(domain_axes: dict[str, str], combo: dict[str, str]) -> list[str]:
    """이 생성기가 직접 구현하지 않은 축은 적용된 지침을 적어 보여준다."""
    handled = {"length", "formality", "structure", "sentiment"}
    notes = []
    for name, instruction in domain_axes.items():
        if name in handled or not instruction:
            continue
        notes.append(instruction)
    return notes


def generate_demo(source_text: str, combo: dict[str, str], domain=None) -> str:
    keywords = _keywords(source_text)
    has_sentiment_axis = domain is not None and any(
        axis.name == "sentiment" for axis in domain.axes
    )
    lines = _apply_formality(_sentences(combo, keywords, has_sentiment_axis, source_text), combo)

    if combo.get("structure") == "bullets":
        body = "\n".join(f"- {line}" for line in lines)
    else:
        body = " ".join(lines)

    # 구현하지 않은 축(예: 자유 키워드 주제)이 활성이면 그 지침을 덧붙인다.
    if domain is not None:
        instructions = {}
        for axis in domain.axes:
            value = combo.get(axis.name, "")
            try:
                instructions[axis.name] = axis.instruction_for(value) or ""
            except ValueError:
                instructions[axis.name] = ""
        notes = _applied_notes(instructions, combo)
        if notes:
            body += "\n\n" + "\n".join(f"> {note}" for note in notes)

    return body
