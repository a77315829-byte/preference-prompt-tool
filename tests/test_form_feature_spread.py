"""판별력비 계산을 검사한다.

이 함수 하나가 "다음에 무엇을 할지"를 정하는 판정을 내리므로, 분모를
잘못 두면 엉뚱한 방향으로 몇 주를 쓴다. 실제로 첫 판(답변 하나 기준)에서
효과가 확인된 대조군까지 탈락시켰다.
"""

from __future__ import annotations

import math

from experiments.form_feature_spread import TRAIN_N, spread_ratios


def test_identical_groups_have_no_signal() -> None:
    groups = [[1.0, 2.0, 3.0], [1.0, 2.0, 3.0], [1.0, 2.0, 3.0]]
    raw, pooled = spread_ratios(groups)
    assert raw == 0.0
    assert pooled == 0.0


def test_constant_feature_has_no_signal() -> None:
    """코퍼스 전체에서 값이 안 변하면 저자를 구분할 수 없다.

    MACSum 의 bullet_line_ratio 가 정확히 이 경우다 (전부 0.0).
    분모가 0 이므로 0 나누기를 내지 않는지도 같이 본다.
    """
    raw, pooled = spread_ratios([[0.0] * 5, [0.0] * 5, [0.0] * 5])
    assert (raw, pooled) == (0.0, 0.0)


def test_separated_groups_with_zero_within_variance_are_infinite() -> None:
    raw, pooled = spread_ratios([[1.0, 1.0], [5.0, 5.0]])
    assert math.isinf(raw) and math.isinf(pooled)


def test_averaging_lifts_a_noisy_but_separated_feature() -> None:
    """평균 기준이 답변 기준의 TRAIN_N 배여야 한다.

    이게 이 지표의 핵심이다. 저자 안이 시끄러워도 예시를 모아 평균을
    내면 저자를 가를 수 있고, 앵커가 쓰는 값이 바로 그 평균이다.
    """
    groups = [[0.0, 30.0, 60.0], [50.0, 80.0, 110.0]]
    raw, pooled = spread_ratios(groups)
    assert 0 < raw < 2.0  # 답변 하나로는 못 가른다
    assert pooled > 2.0  # 평균으로는 가른다
    assert pooled == raw * TRAIN_N


def test_single_group_cannot_be_compared() -> None:
    assert spread_ratios([[1.0, 2.0]]) == (0.0, 0.0)
    assert spread_ratios([]) == (0.0, 0.0)
