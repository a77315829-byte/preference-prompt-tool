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
    winner: str  # "a", "b", 또는 "tie" (두 후보가 비슷하다)


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
        """한 비교를 반영한다. tie 는 "반쯤 이김"으로 다룬다 - 목표 확률을 0.5 로 두어
        두 값의 효용을 서로 가깝게 당긴다 (Bradley-Terry 에서 무승부를 다루는 흔한 근사).
        효용이 같을 때의 tie 는 아무것도 바꾸지 않는다."""
        if comparison.winner not in ("a", "b", "tie"):
            raise ValueError(f"winner 는 'a', 'b', 'tie' 중 하나여야 한다: {comparison.winner!r}")
        self.history.append(comparison)
        for axis in self._enum_axes:
            value_a = comparison.combo_a.get(axis.name)
            value_b = comparison.combo_b.get(axis.name)
            if value_a is None or value_b is None or value_a == value_b:
                continue

            u = self.utilities[axis.name]
            p_a_wins = 1.0 / (1.0 + math.exp(-(u[value_a] - u[value_b])))
            target = {"a": 1.0, "b": 0.0, "tie": 0.5}[comparison.winner]
            grad = target - p_a_wins
            u[value_a] += self.learning_rate * grad
            u[value_b] -= self.learning_rate * grad

    def preferred_value(self, axis_name: str) -> str:
        utilities = self.utilities[axis_name]
        return max(utilities, key=utilities.get)

    def has_signal(self, axis_name: str) -> bool:
        """이 축에서 값들 사이에 차이가 생겼는가. 모든 효용이 같으면 preferred_value 는
        단지 정의 순서상 첫 값이다 - 비교가 없었거나 "비슷하다"만 골랐을 때다. 그 값을
        사용자의 선호로 내보내면 하지 않은 선택을 했다고 적게 된다."""
        return len(set(self.utilities[axis_name].values())) > 1

    def confidence(self, axis_name: str) -> float:
        """softmax 분포가 얼마나 뾰족한지 (1 - 정규화 엔트로피). 1이면 확신, 0이면 무지.

        **확률이 아니다.** "사용자의 선호가 이 값일 확률"(사후확률)이 아니라, 추정한
        효용이 한 값으로 얼마나 쏠렸는지를 재는 상대 지표다. 그래서 축끼리 가중치를
        비교하는 데(metric_builder)만 쓰고 사용자에게 보여 주지 않는다 - 값이 3개인
        축은 24번 물어도 0.06 근처에 머물면서 선호는 정확히 복원한다 (CLAUDE.md 보너스 3)."""
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
