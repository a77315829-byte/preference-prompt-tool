"""도메인: 문서 요약 (한국어). 축별 검사 함수.

engine/metric_builder.py 가 domains/summarization_ko.yaml 의 check.fn
이름으로 이 모듈에서 함수를 동적으로 찾아 호출한다. 시그니처는
checks/summarization.py와 동일: fn(output, source, value, target) ->
(score: float, feedback: str)

checks/summarization.py와의 차이: 한국어는 조사가 붙어 "정부는/정부가"가
표면형으로는 다른 토큰이 된다. 내용어(명사·동사·형용사·부사·어근)만
남기고 조사·어미·기호를 버린 뒤 비교해 이 문제를 피한다.

형태소 분석 백엔드가 두 개다.
- kiwi: Kiwi(`kiwipiepy`) 형태소 분석기. **실험·논문 수치는 전부 이쪽**이다.
- regex: 순수 파이썬 근사. 문자 4-gram 겹침으로 형태소 겹침을 대신한다.

왜 두 개인가: Kiwi는 모델 데이터가 88MB이고 Kiwi() 생성 시 램에 올라간다.
Streamlit Community Cloud 무료 티어에서 이걸 감당하기 어려워 배포용
requirements.txt에는 kiwipiepy를 넣지 않는다. 배포된 앱에서 GEPA 최적화가
한국어에서도 동작하려면 fallback이 필요하다. 두 백엔드의 겹침 비율이
서로 가깝다는 것은 tests/test_korean_checks_backends.py 에서 실측으로
확인한다 (YAML 임계값 0.5/0.75가 양쪽에서 같은 의미여야 하므로).

`active_backend()` 로 지금 어느 쪽이 쓰이는지 확인할 수 있다. 실험을
돌리는 환경에서 백엔드가 조용히 regex로 내려앉는 일이 없도록
tests 에서 이 값을 검사한다.
"""

from __future__ import annotations

import re

_CONTENT_TAG_PREFIXES = ("NNG", "NNP", "NNB", "VV", "VA", "MAG", "XR", "SL", "SN")

_kiwi = None
_backend: str | None = None


def _ensure_backend() -> str:
    """첫 호출 시 Kiwi를 시도하고, 없으면 regex 근사로 내려앉는다.

    import 시점이 아니라 실제 사용 시점에 한 번만 로드한다 - Kiwi()는
    모델을 램에 올리므로 이 모듈을 import만 하는 경로에서 비용을 물지
    않게 한다.
    """
    global _kiwi, _backend
    if _backend is not None:
        return _backend
    try:
        from kiwipiepy import Kiwi
    except ImportError:
        _backend = "regex"
        return _backend
    _kiwi = Kiwi()
    _backend = "kiwi"
    return _backend


def active_backend() -> str:
    """현재 쓰이는 형태소 분석 백엔드 이름 ("kiwi" 또는 "regex")."""
    return _ensure_backend()


# --- 문자 3-gram fallback ---------------------------------------------------

# 왜 형태소 대신 문자 n-gram인가: 사전 없이 어절 끝 조사를 규칙으로 잘라내려
# 하면 "전문가"의 "가"를 주격 조사로 오인해 어간을 망가뜨린다(실측: 중간
# 대역에서 겹침이 0.59 -> 0.47로 내려가 임계값 0.5를 잘못 넘었다). 한국어는
# 조사가 어절 뒤에 붙으므로 "정부는"과 "정부가"는 문자 n-gram을 대부분
# 공유한다 - 사전 없이 조사 변화에 둔감해지는 표준적인 방법이다.
#
# n=4를 고른 근거는 Kiwi 형태소 bigram 겹침과의 실측 일치도다 (한국어 원문
# 3종 x 발췌 문장수 4단계 x 어절 누락률 6단계 = 72케이스, YAML 임계값
# 0.5/0.75로 라벨을 매겨 비교):
#
#   n=2  57%   n=3  67%   n=4  97%   n=5  82%   n=6  74%
#
# n=4는 평균 오차 0.035, 피어슨 r=0.977이고 Kiwi 값으로의 최소제곱 회귀
# 기울기가 1.07/절편 -0.07 - 거의 항등이라 별도 보정 상수가 필요 없다.
# 그래서 같은 YAML 임계값을 두 백엔드가 그대로 공유한다. 남은 불일치
# 2건은 어절을 대량 누락시킨 비문이고 둘 다 대역 경계값(0.71 vs 0.75,
# 0.43 vs 0.50)이다. 재현: tests/test_korean_checks_backends.py
_CHAR_NGRAM_N = 4

_NON_CONTENT_RE = re.compile(r"[^가-힣A-Za-z0-9]+")


def _char_ngrams(text: str) -> set[str]:
    stripped = _NON_CONTENT_RE.sub("", text.lower())
    n = _CHAR_NGRAM_N
    return {stripped[i : i + n] for i in range(len(stripped) - n + 1)}


_SENT_SPLIT_RE = re.compile(r"(?<=[.!?。])\s+")


def _sentences_regex(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text.strip())
    if not normalized:
        return []
    return [part.strip() for part in _SENT_SPLIT_RE.split(normalized) if part.strip()]


# --- 공통 진입점 ------------------------------------------------------------


def _sentences(text: str) -> list[str]:
    if _ensure_backend() == "kiwi":
        return [s.text for s in _kiwi.split_into_sents(text.strip())]
    return _sentences_regex(text)


def _content_morphemes(text: str) -> list[str]:
    """Kiwi 백엔드 전용. regex 백엔드에서는 _char_ngrams 를 쓴다."""
    return [t.form for t in _kiwi.tokenize(text) if t.tag.startswith(_CONTENT_TAG_PREFIXES)]


def _overlap_ratio(output: str, source: str) -> float:
    """요약이 원문 표현을 그대로 가져온 비율. 백엔드에 따라 단위가 다르다
    (kiwi: 내용 형태소 bigram, regex: 문자 4-gram). 두 단위의 값이 실측으로
    거의 일치하므로 YAML 임계값을 공유한다."""
    if _ensure_backend() == "kiwi":
        out_units = _bigrams(_content_morphemes(output))
        src_units = _bigrams(_content_morphemes(source))
    else:
        out_units = _char_ngrams(output)
        src_units = _char_ngrams(source)
    return len(out_units & src_units) / len(out_units) if out_units else 0.0


def _bigrams(tokens: list[str]) -> set[tuple[str, str]]:
    return set(zip(tokens, tokens[1:]))


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
    overlap = _overlap_ratio(output, source)

    min_o = target.get("min_overlap")
    max_o = target.get("max_overlap")

    if min_o is not None and overlap < min_o:
        return max(0.0, overlap / min_o), (
            f"추출성 위반: 원문과의 형태소 겹침 {overlap:.0%} (목표 {min_o:.0%} 이상). "
            "원문 표현을 더 그대로 사용하라."
        )
    if max_o is not None and overlap > max_o:
        excess = overlap - max_o
        return max(0.0, 1.0 - 2 * excess), (
            f"추출성 위반: 원문과의 형태소 겹침 {overlap:.0%} (목표 {max_o:.0%} 이하). "
            "표현을 더 바꿔 써라."
        )
    return 1.0, f"추출성 충족: 원문과의 형태소 겹침 {overlap:.0%}."


def keyword_presence(output: str, source: str, value: str, target: dict) -> tuple[float, str]:
    if not value:
        return 1.0, "주제 축 비활성 (해당 없음)."
    if value in output:
        return 1.0, f"주제 충족: '{value}' 언급됨."
    return 0.0, f"주제 위반: '{value}'가 요약에 없음."
