"""다음에 보여줄 쌍 선택 알고리즘 - 무작위, 축 순차 질의, 불확실도 기반.

이 모듈도 축에 고정된 값 집합이 있는지(enum) 아닌지(freeform)만 구분할
뿐, 어떤 도메인인지는 모른다.
"""

from __future__ import annotations

import itertools
import random
from collections import deque

from engine.domain_loader import Domain
from engine.estimator import Estimator

Combo = dict[str, str]
Pair = tuple[Combo, Combo]


def _baseline_combo(domain: Domain, estimator: Estimator) -> Combo:
    """현재까지의 최선 추정값으로 채운 콤보. freeform 축은 비활성값(빈 문자열)."""
    combo: Combo = {}
    for axis in domain.axes:
        combo[axis.name] = estimator.preferred_value(axis.name) if axis.type == "enum" else ""
    return combo


class RandomSelector:
    def __init__(self, domain: Domain, seed: int = 0) -> None:
        self.domain = domain
        self._enum_axes = [axis for axis in domain.axes if axis.type == "enum"]
        self._rng = random.Random(seed)

    def _random_combo(self) -> Combo:
        combo: Combo = {}
        for axis in self.domain.axes:
            if axis.type == "enum":
                combo[axis.name] = self._rng.choice([v.value for v in axis.values])
            else:
                combo[axis.name] = ""
        return combo

    def next_pair(self, estimator: Estimator) -> Pair:
        return self._random_combo(), self._random_combo()


class SequentialAxisSelector:
    """축을 정해진 순서로 하나씩, 그 축의 값 쌍을 모두 소진할 때까지 질의한다.
    다른 축은 현재까지의 최선 추정값(baseline)으로 고정한다."""

    def __init__(self, domain: Domain, seed: int = 0) -> None:
        self.domain = domain
        self._enum_axes = [axis for axis in domain.axes if axis.type == "enum"]
        self._rng = random.Random(seed)
        self._axis_idx = 0
        self._pair_queue: deque[tuple[str, str]] = deque()
        self._load_queue_for_current_axis()

    def _load_queue_for_current_axis(self) -> None:
        axis = self._enum_axes[self._axis_idx % len(self._enum_axes)]
        pairs = list(itertools.combinations([v.value for v in axis.values], 2))
        self._rng.shuffle(pairs)
        self._pair_queue = deque(pairs)

    def next_pair(self, estimator: Estimator) -> Pair:
        while not self._pair_queue:
            self._axis_idx += 1
            self._load_queue_for_current_axis()

        axis = self._enum_axes[self._axis_idx % len(self._enum_axes)]
        value_a, value_b = self._pair_queue.popleft()

        combo_a = _baseline_combo(self.domain, estimator)
        combo_b = dict(combo_a)
        combo_a[axis.name] = value_a
        combo_b[axis.name] = value_b
        return combo_a, combo_b


class UncertaintySelector:
    """확신도가 가장 낮은 축을 고르고, 그 축에서 utility가 가장 근접한
    (가장 헷갈리는) 두 값을 질의한다. 다른 축은 baseline으로 고정한다."""

    def __init__(self, domain: Domain, seed: int = 0) -> None:
        self.domain = domain
        self._enum_axes = [axis for axis in domain.axes if axis.type == "enum"]
        self._rng = random.Random(seed)

    def _pick_axis_name(self, estimator: Estimator) -> str:
        confidences = {axis.name: estimator.confidence(axis.name) for axis in self._enum_axes}
        min_confidence = min(confidences.values())
        candidates = [name for name, c in confidences.items() if c == min_confidence]
        return self._rng.choice(candidates)

    def _most_confusable_pair(self, estimator: Estimator, axis_name: str) -> tuple[str, str]:
        ordered = sorted(estimator.utilities[axis_name].items(), key=lambda kv: kv[1])
        gaps = [
            (abs(ordered[i + 1][1] - ordered[i][1]), ordered[i][0], ordered[i + 1][0])
            for i in range(len(ordered) - 1)
        ]
        _, value_a, value_b = min(gaps, key=lambda g: g[0])
        return value_a, value_b

    def next_pair(self, estimator: Estimator) -> Pair:
        axis_name = self._pick_axis_name(estimator)
        value_a, value_b = self._most_confusable_pair(estimator, axis_name)

        combo_a = _baseline_combo(self.domain, estimator)
        combo_b = dict(combo_a)
        combo_a[axis_name] = value_a
        combo_b[axis_name] = value_b
        return combo_a, combo_b
