"""한국어 checks의 두 형태소 백엔드(Kiwi / 문자 4-gram)가 같은 YAML
임계값에서 같은 판정을 내리는지 검증.

왜 필요한가: domains/summarization_ko.yaml 의 extractiveness 임계값
(0.5 / 0.75)은 Kiwi 형태소 bigram 겹침으로 보정된 값이다. 배포
환경(Streamlit Community Cloud)에는 kiwipiepy를 넣지 않으므로 문자
4-gram fallback이 쓰이는데, 이쪽이 다른 스케일이면 GEPA가 엉뚱한
추출성으로 최적화된다.

두 가지를 잠근다.
1. kiwipiepy가 깔린 환경에서는 반드시 kiwi 백엔드가 쓰인다 (실험 수치가
   조용히 fallback으로 내려앉는 사고 방지).
2. 두 백엔드의 임계값 라벨 일치율이 90% 이상이다.
"""

import importlib
import random
import statistics
import sys

import pytest


SOURCES = [
    "정부는 15일 수도권 주택 공급을 늘리기 위한 대책을 발표했다. "
    "국토교통부에 따르면 2026년까지 신규 택지 12만 가구가 공급된다. "
    "전문가들은 이번 대책이 단기 가격 안정에는 제한적인 효과를 낼 것으로 전망했다. "
    "시민단체는 임대주택 비중이 지나치게 낮다고 비판했다. "
    "국토교통부는 추가 대책을 연말까지 마련하겠다고 밝혔다.",
    "연구팀은 새로운 촉매를 이용해 이산화탄소를 메탄올로 전환하는 효율을 두 배로 높였다고 발표했다. "
    "실험은 상온 상압 조건에서 진행됐으며 기존 공정보다 에너지 소비가 적었다. "
    "논문은 국제 학술지에 게재됐다. "
    "연구팀은 상용화까지 최소 5년이 걸릴 것으로 예상했다. "
    "산업계는 설비 교체 비용을 우려하고 있다.",
    "중앙은행은 기준금리를 0.25%포인트 인상했다. "
    "물가 상승률이 목표치를 크게 웃돈 데 따른 조치다. "
    "시장은 추가 인상 가능성을 주시하고 있다. "
    "가계 대출 이자 부담이 늘어날 것으로 보인다. "
    "총재는 향후 결정은 지표에 따라 달라진다고 말했다.",
]

# YAML(domains/summarization_ko.yaml)의 extractiveness 임계값과 같은 값.
HIGH_MIN, FULLY_MIN = 0.5, 0.75

MIN_LABEL_AGREEMENT = 0.90


def _label(overlap: float) -> str:
    if overlap >= FULLY_MIN:
        return "fully"
    if overlap >= HIGH_MIN:
        return "high"
    return "normal"


def _load(force_regex: bool):
    """checks.summarization_ko 를 원하는 백엔드로 새로 로드한다."""
    sys.modules.pop("checks.summarization_ko", None)
    if force_regex:
        # import kiwipiepy 가 ImportError를 내도록 만든다.
        sys.modules["kiwipiepy"] = None
    else:
        if sys.modules.get("kiwipiepy", "x") is None:
            del sys.modules["kiwipiepy"]
    module = importlib.import_module("checks.summarization_ko")
    module._ensure_backend()
    return module


@pytest.fixture
def restore_modules():
    yield
    if sys.modules.get("kiwipiepy", "x") is None:
        del sys.modules["kiwipiepy"]
    sys.modules.pop("checks.summarization_ko", None)


def _cases() -> list[tuple[str, str]]:
    """원문에서 앞쪽 N문장을 발췌하고 어절 일부를 누락시켜, 추출성이
    1.0에서 0에 가깝게 내려가는 연속 구간을 만든다."""
    rng = random.Random(0)
    cases = []
    for source in SOURCES:
        sentences = [s.strip() for s in source.split(". ") if s.strip()]
        for keep in (1, 2, 3, 5):
            for drop_p in (0.0, 0.1, 0.2, 0.35, 0.5, 0.65):
                kept = []
                for sentence in sentences[:keep]:
                    words = [w for w in sentence.split() if rng.random() > drop_p]
                    if words:
                        kept.append(" ".join(words))
                cases.append((source, ". ".join(kept) + "."))
    return cases


def test_kiwi_is_used_when_available(restore_modules) -> None:
    """kiwipiepy가 깔려 있으면 반드시 kiwi 백엔드여야 한다.

    실험·보고 수치는 전부 kiwi 기준이다. 여기서 regex가 나오면
    실험 환경이 조용히 fallback으로 내려앉은 것이므로 실패시킨다."""
    pytest.importorskip("kiwipiepy")
    assert _load(force_regex=False).active_backend() == "kiwi"


def test_regex_fallback_activates_without_kiwi(restore_modules) -> None:
    """kiwipiepy가 없어도 import 실패 없이 동작해야 한다 (배포 경로)."""
    module = _load(force_regex=True)
    assert module.active_backend() == "regex"
    score, feedback = module.lexical_overlap(
        SOURCES[0], SOURCES[0], "fully", {"min_overlap": FULLY_MIN}
    )
    assert score == 1.0
    assert "추출성" in feedback


def test_both_backends_agree_on_yaml_thresholds(restore_modules) -> None:
    """같은 임계값에서 두 백엔드의 판정이 90% 이상 일치해야 한다."""
    pytest.importorskip("kiwipiepy")
    cases = _cases()

    kiwi_module = _load(force_regex=False)
    assert kiwi_module.active_backend() == "kiwi"
    kiwi_values = [kiwi_module._overlap_ratio(out, src) for src, out in cases]

    regex_module = _load(force_regex=True)
    assert regex_module.active_backend() == "regex"
    regex_values = [regex_module._overlap_ratio(out, src) for src, out in cases]

    agreement = statistics.fmean(
        float(_label(k) == _label(r)) for k, r in zip(kiwi_values, regex_values)
    )
    mean_error = statistics.fmean(abs(k - r) for k, r in zip(kiwi_values, regex_values))

    assert agreement >= MIN_LABEL_AGREEMENT, (
        f"백엔드 판정 일치율 {agreement:.0%} < {MIN_LABEL_AGREEMENT:.0%}. "
        f"_CHAR_NGRAM_N 재보정이 필요하다 (평균 오차 {mean_error:.3f})."
    )
    assert mean_error < 0.1


def test_sentence_count_matches_across_backends(restore_modules) -> None:
    """길이 축도 두 백엔드에서 같은 문장 수를 세야 한다."""
    pytest.importorskip("kiwipiepy")
    kiwi_module = _load(force_regex=False)
    kiwi_counts = [len(kiwi_module._sentences(s)) for s in SOURCES]

    regex_module = _load(force_regex=True)
    regex_counts = [len(regex_module._sentences(s)) for s in SOURCES]

    assert kiwi_counts == regex_counts == [5, 5, 5]
