"""선택 이력 -> 축별 선호 + 확신도 추정. Bradley-Terry 스타일 온라인 학습.

이 모듈은 축에 고정된 값 집합이 있는지(enum) 아닌지(freeform)만 구분할
뿐, 어떤 도메인인지는 모른다. 값이 고정되지 않은 축은 선호를 학습할
대상 자체가 없으므로 다루지 않는다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from engine.domain_loader import Domain


@dataclass
class Comparison:
    combo_a: dict[str, str]
    combo_b: dict[str, str]
    winner: str  # "a" 또는 "b"


class Estimator:
    def __init__(self, domain: Domain, learning_rate: float = 0.5) -> None:
        self.domain = domain
        self.learning_rate = learning_rate
        self._enum_axes = [axis for axis in domain.axes if axis.type == "enum"]
        self.utilities: dict[str, dict[str, float]] = {
            axis.name: {v.value: 0.0 for v in axis.values} for axis in self._enum_axes
        }
        self.history: list[Comparison] = []

    def update(self, comparison: Comparison) -> None:
        self.history.append(comparison)
        for axis in self._enum_axes:
            value_a = comparison.combo_a.get(axis.name)
            value_b = comparison.combo_b.get(axis.name)
            if value_a is None or value_b is None or value_a == value_b:
                continue

            u = self.utilities[axis.name]
            p_a_wins = 1.0 / (1.0 + math.exp(-(u[value_a] - u[value_b])))
            grad = (1.0 - p_a_wins) if comparison.winner == "a" else -p_a_wins
            u[value_a] += self.learning_rate * grad
            u[value_b] -= self.learning_rate * grad

    def preferred_value(self, axis_name: str) -> str:
        utilities = self.utilities[axis_name]
        return max(utilities, key=utilities.get)

    def confidence(self, axis_name: str) -> float:
        """softmax 분포가 얼마나 뾰족한지 (1 - 정규화 엔트로피). 1이면 확신, 0이면 무지."""
        values = list(self.utilities[axis_name].values())
        k = len(values)
        if k <= 1:
            return 1.0

        max_u = max(values)
        exps = [math.exp(v - max_u) for v in values]
        total = sum(exps)
        probs = [e / total for e in exps]
        entropy = -sum(p * math.log(p) for p in probs if p > 0)
        return 1.0 - entropy / math.log(k)

    def enum_axis_names(self) -> list[str]:
        return [axis.name for axis in self._enum_axes]
