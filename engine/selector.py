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
    (가장 헷갈리는) 두 값을 질의한다. 다른 축은 baseline으로 고정한다.

    같은 (축, 값쌍)은 한 번만 묻는다. 원래 구현엔 이력이 없어서 - 매
    라운드 "지금 상태에서 가장 헷갈리는 쌍"을 처음부터 다시 계산할
    뿐이라 - 확신도가 안 바뀌면 같은 질문이 반복될 수 있었다(FR-03 "같은
    질문 반복 금지"가 실제로는 보장되지 않고 있었다). 한 축의 모든 쌍을
    다 물었으면 그다음으로 확신도가 낮은 축으로 넘어가고, 축 전부가
    소진된 드문 경우에만 반복을 허용한다."""

    def __init__(self, domain: Domain, seed: int = 0) -> None:
        self.domain = domain
        self._enum_axes = [axis for axis in domain.axes if axis.type == "enum"]
        self._rng = random.Random(seed)
        self._asked: set[tuple[str, str, str]] = set()

    def _pair_key(self, axis_name: str, value_a: str, value_b: str) -> tuple[str, str, str]:
        low, high = sorted((value_a, value_b))
        return (axis_name, low, high)

    def _axis_has_unasked_pair(self, axis) -> bool:
        values = [v.value for v in axis.values]
        return any(
            self._pair_key(axis.name, a, b) not in self._asked
            for a, b in itertools.combinations(values, 2)
        )

    def _pick_axis_name(self, estimator: Estimator) -> str:
        eligible = [axis for axis in self._enum_axes if self._axis_has_unasked_pair(axis)]
        pool = eligible or self._enum_axes  # 전부 소진되면 반복을 허용한다
        confidences = {axis.name: estimator.confidence(axis.name) for axis in pool}
        min_confidence = min(confidences.values())
        candidates = [name for name, c in confidences.items() if c == min_confidence]
        return self._rng.choice(candidates)

    def _most_confusable_pair(self, estimator: Estimator, axis_name: str) -> tuple[str, str]:
        axis = next(a for a in self._enum_axes if a.name == axis_name)
        values = [v.value for v in axis.values]
        utilities = estimator.utilities[axis_name]

        def gaps(only_unasked: bool):
            return [
                (abs(utilities[a] - utilities[b]), a, b)
                for a, b in itertools.combinations(values, 2)
                if not only_unasked or self._pair_key(axis_name, a, b) not in self._asked
            ]

        candidates = gaps(only_unasked=True) or gaps(only_unasked=False)
        _, value_a, value_b = min(candidates, key=lambda g: g[0])
        return value_a, value_b

    def next_pair(self, estimator: Estimator) -> Pair:
        axis_name = self._pick_axis_name(estimator)
        value_a, value_b = self._most_confusable_pair(estimator, axis_name)
        self._asked.add(self._pair_key(axis_name, value_a, value_b))

        combo_a = _baseline_combo(self.domain, estimator)
        combo_b = dict(combo_a)
        combo_a[axis_name] = value_a
        combo_b[axis_name] = value_b
        return combo_a, combo_b
