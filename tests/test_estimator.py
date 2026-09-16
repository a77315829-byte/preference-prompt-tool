"""engine/estimator.py 회귀 테스트.

이 모듈은 CLAUDE.md 가 "라이브러리로 대체 불가능한 핵심 기여"로 표시한
것인데 전용 테스트 파일이 없었다. API 호출은 하지 않는다 - 선택 이력에서
선호를 추정하는 순수 계산이다.
"""

import math

import pytest

from engine.domain_loader import load_domain
from engine.estimator import Comparison, Estimator


@pytest.fixture(scope="module")
def domain():
    # length(3값) / extractiveness(3값) / topic(자유 키워드)
    return load_domain("domains/summarization.yaml")


@pytest.fixture
def estimator(domain):
    return Estimator(domain)


def _combo(length: str, extractiveness: str) -> dict[str, str]:
    return {"length": length, "extractiveness": extractiveness, "topic": ""}


def test_freeform_axes_are_not_learned(estimator) -> None:
    """값이 고정되지 않은 축은 학습 대상이 아니다. topic 은 자유 키워드다."""
    assert "topic" not in estimator.enum_axis_names()
    assert set(estimator.enum_axis_names()) == {"length", "extractiveness"}


def test_starts_with_no_information(estimator) -> None:
    """선택이 없으면 모든 값의 효용이 같고 확신도는 0이어야 한다."""
    for name in estimator.enum_axis_names():
        assert estimator.confidence(name) == pytest.approx(0.0, abs=1e-9)
        assert len(set(estimator.utilities[name].values())) == 1


def test_repeated_wins_make_a_value_preferred(estimator) -> None:
    for _ in range(5):
        estimator.update(Comparison(_combo("short", "fully"), _combo("long", "fully"), "a"))
    assert estimator.preferred_value("length") == "short"


def test_winner_side_does_not_matter(domain) -> None:
    """같은 정보를 A쪽/B쪽으로 주면 같은 결론이 나와야 한다.

    부호를 한쪽만 갱신하는 실수를 하면 여기서 갈린다.
    """
    left = Estimator(domain)
    right = Estimator(domain)
    for _ in range(5):
        left.update(Comparison(_combo("short", "fully"), _combo("long", "fully"), "a"))
        right.update(Comparison(_combo("long", "fully"), _combo("short", "fully"), "b"))

    assert left.preferred_value("length") == right.preferred_value("length") == "short"
    assert left.utilities["length"] == pytest.approx(right.utilities["length"])


def test_axis_not_varied_is_left_untouched(estimator) -> None:
    """두 후보가 같은 값을 가진 축은 갱신하지 않는다. 그 비교는 그 축에
    대해 아무 정보도 주지 않기 때문이다."""
    before = dict(estimator.utilities["extractiveness"])
    for _ in range(5):
        estimator.update(Comparison(_combo("short", "fully"), _combo("long", "fully"), "a"))
    assert estimator.utilities["extractiveness"] == before


def test_conflicting_choices_leave_confidence_near_zero(domain) -> None:
    """엇갈린 선택은 확신도를 끌어올리지 못해야 한다.

    정확히 0으로 상쇄되지는 않는다. 온라인 갱신이라 기울기가 직전 효용에
    따라 달라져서, 같은 쌍을 a/b 번갈아 골라도 잔차가 남는다(실측 0.005).
    의미 있는 성질은 "일관된 선택보다 훨씬 낮다"이므로 그걸 검사한다.
    """
    conflicting = Estimator(domain)
    consistent = Estimator(domain)
    for _ in range(4):
        conflicting.update(Comparison(_combo("short", "fully"), _combo("long", "fully"), "a"))
        conflicting.update(Comparison(_combo("short", "fully"), _combo("long", "fully"), "b"))
        consistent.update(Comparison(_combo("short", "fully"), _combo("long", "fully"), "a"))
        consistent.update(Comparison(_combo("short", "fully"), _combo("long", "fully"), "a"))

    assert conflicting.confidence("length") < 0.02
    assert conflicting.confidence("length") < consistent.confidence("length") / 5


def test_confidence_rises_with_consistent_evidence(estimator) -> None:
    """일관된 증거가 쌓이면 확신도는 단조 증가해야 한다.

    절대값은 작게 머문다 - 사용자에게 보여줄 만큼 보정된 값이 아니라는
    것은 CLAUDE.md 보너스 3에 실측과 함께 기록해뒀다. 여기서는 방향만 본다.
    """
    seen = []
    for _ in range(6):
        estimator.update(Comparison(_combo("short", "fully"), _combo("long", "fully"), "a"))
        seen.append(estimator.confidence("length"))
    assert all(b >= a for a, b in zip(seen, seen[1:])), seen
    assert seen[-1] > seen[0]


def test_confidence_stays_in_unit_range(estimator) -> None:
    for _ in range(40):
        estimator.update(Comparison(_combo("short", "fully"), _combo("long", "normal"), "a"))
    for name in estimator.enum_axis_names():
        value = estimator.confidence(name)
        assert 0.0 <= value <= 1.0
        assert math.isfinite(value)


def test_history_is_recorded(estimator) -> None:
    """이력은 그대로 보관돼야 한다. 사후 분석과 재현에 쓰인다."""
    comparisons = [
        Comparison(_combo("short", "fully"), _combo("long", "normal"), "a"),
        Comparison(_combo("normal", "high"), _combo("long", "normal"), "b"),
    ]
    for comparison in comparisons:
        estimator.update(comparison)
    assert estimator.history == comparisons


def test_unknown_axis_raises(estimator) -> None:
    with pytest.raises(KeyError):
        estimator.preferred_value("speaker")


def test_three_way_axis_ranks_all_values(estimator) -> None:
    """3값 축에서 중간 값이 양 끝보다 선호되는 것도 표현할 수 있어야 한다."""
    for _ in range(6):
        estimator.update(Comparison(_combo("normal", "fully"), _combo("short", "fully"), "a"))
        estimator.update(Comparison(_combo("normal", "fully"), _combo("long", "fully"), "a"))
    assert estimator.preferred_value("length") == "normal"
