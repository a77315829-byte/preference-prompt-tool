"""앵커를 붙일지 가르는 판정과 임계값 스윕을 검사한다.

이 판정이 틀리면 조용히 나빠진다 - 도움이 되는 저자에게서 앵커를 빼도
결과는 그냥 "base 수준"이라 실패로 안 보인다. 그래서 두 가지를 고정한다.
판정이 학습 자료만 쓰는지, 그리고 스윕이 기준선을 제대로 두는지.
"""

from __future__ import annotations

from agents.expert_onboarding import ExpertExample, length_gap
from experiments.anchor_gating import THRESHOLDS, sweep


def _examples(words: int, count: int = 5) -> list[ExpertExample]:
    return [
        ExpertExample(output=" ".join(["w"] * words), task=" ".join(["q"] * 200))
        for _ in range(count)
    ]


def test_gap_is_near_zero_when_the_model_already_writes_that_length() -> None:
    """실제로 물린 경우다 - 저자 212단어, 모델 기본 출력 215단어."""
    assert length_gap(_examples(212), _examples(215)) < 0.03


def test_gap_is_large_when_the_model_is_far_off() -> None:
    """저자 356단어에 기본 출력 121단어였던 저자. 앵커가 가장 크게 도왔다."""
    assert length_gap(_examples(356), _examples(121)) > 0.6


def test_gap_is_symmetric_in_direction() -> None:
    """모델이 너무 길게 쓰든 너무 짧게 쓰든 지시할 이유는 같다."""
    assert length_gap(_examples(100), _examples(200)) == length_gap(
        _examples(200), _examples(100)
    )


def test_gap_survives_empty_inputs() -> None:
    assert length_gap([], _examples(200)) == 1.0
    assert length_gap(_examples(200), []) == 1.0
    assert length_gap([], []) == 0.0


def test_sweep_baseline_always_applies_the_anchor() -> None:
    """임계값 0 은 아무도 안 걸러내야 한다. 비교의 기준선이 흔들리면
    게이팅이 값을 하는지 알 수 없다."""
    rows = [
        {"site": "s", "user_id": 1, "length_gap": 0.0,
         "form_distance": {"base": 0.20, "stable": 0.10}},
        {"site": "s", "user_id": 2, "length_gap": 0.5,
         "form_distance": {"base": 0.30, "stable": 0.15}},
    ]
    first = sweep(rows)[0]
    assert first["threshold"] == 0.0
    assert first["gated_count"] == 0
    assert first["mean_form_distance"] == 0.125  # stable 만 쓴 평균


def test_sweep_drops_only_authors_under_the_threshold() -> None:
    rows = [
        # 격차가 작고 앵커가 해로운 저자 - 걸러내야 한다.
        {"site": "s", "user_id": 1, "length_gap": 0.02,
         "form_distance": {"base": 0.10, "stable": 0.30}},
        # 격차가 있고 앵커가 이로운 저자 - 남겨야 한다.
        {"site": "s", "user_id": 2, "length_gap": 0.20,
         "form_distance": {"base": 0.40, "stable": 0.10}},
    ]
    entries = {e["threshold"]: e for e in sweep(rows)}
    assert entries[0.0]["mean_form_distance"] == 0.20  # 0.30, 0.10
    assert entries[0.05]["gated"] == ["s/u1"]
    assert entries[0.05]["mean_form_distance"] == 0.10  # 0.10, 0.10
    # 임계값을 너무 올리면 이로운 저자까지 걸러내 다시 나빠진다.
    assert entries[0.25]["gated"] == ["s/u1", "s/u2"]
    assert entries[0.05]["mean_form_distance"] < entries[0.25]["mean_form_distance"]


def test_sweep_covers_the_measured_gap_range() -> None:
    """실측 격차가 0.015~0.66 에 퍼져 있다. 스윕이 그 아래쪽을 촘촘히
    덮어야 판정 경계를 찾을 수 있다."""
    assert min(THRESHOLDS) == 0.0
    assert max(THRESHOLDS) >= 0.25
    assert sum(1 for t in THRESHOLDS if t <= 0.15) >= 5


def test_holdout_offset_must_not_overlap_training() -> None:
    """홀드아웃이 학습과 겹치면 결과가 전부 무의미해진다. API 호출 전에 막는다."""
    import pytest

    from experiments.anchor_gating import run_author

    author = {
        "user_id": 1,
        "pairs": [{"answer": f"Answer {i}.", "task": f"Task {i}"} for i in range(40)],
    }
    with pytest.raises(SystemExit, match="앞이다"):
        run_author("site", author, n_train=12, n_test=5, holdout_offset=6)


def test_holdout_shortage_is_reported_not_silently_truncated() -> None:
    """조용히 짧은 홀드아웃으로 돌면 저자마다 표본 크기가 달라진다."""
    import pytest

    from experiments.anchor_gating import run_author

    author = {
        "user_id": 1,
        "pairs": [{"answer": f"Answer {i}.", "task": f"Task {i}"} for i in range(20)],
    }
    with pytest.raises(SystemExit, match="홀드아웃이 부족"):
        run_author("site", author, n_train=12, n_test=45)
