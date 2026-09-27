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


def _pair_key(combo_a: Combo, combo_b: Combo) -> frozenset:
    """A/B 순서와 무관한 쌍의 식별자. 뒤집어 보여줘도 같은 질문이다."""
    return frozenset(
        (tuple(sorted(combo_a.items())), tuple(sorted(combo_b.items())))
    )


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

    사람을 상대하는 화면을 위한 선택 사항이 두 개 있다. 둘 다 기본은 꺼져
    있고, 꺼져 있으면 동작이 예전과 똑같다 - 실험 결과(experiments/results)
    는 이 기본 동작으로 낸 것이다.

    - contrast_first: 아직 한 번도 갈라 본 적 없는 축은 양 끝 값(YAML 의
      첫 값과 마지막 값)부터 묻는다. 처음에는 모든 효용이 0이라 "가장
      헷갈리는 쌍"이 곧 이웃한 두 값이 되고, 사람 눈에는 A/B 가 거의 같아
      보인다 (요약의 normal 대 high 추출성).
    - avoid_repeats: 이미 물은 쌍(A/B 순서 무관)은 다시 묻지 않는다. 값이
      2개뿐인 축은 가능한 쌍이 하나라서, 막지 않으면 같은 질문이 몇 번이고
      나온다. 같은 축을 다시 물어야 하면 다른 축의 값을 바꿔 새 쌍을 만든다.
    """

    def __init__(
        self,
        domain: Domain,
        seed: int = 0,
        *,
        contrast_first: bool = False,
        avoid_repeats: bool = False,
    ) -> None:
        self.domain = domain
        self._enum_axes = [axis for axis in domain.axes if axis.type == "enum"]
        self._rng = random.Random(seed)
        self.contrast_first = contrast_first
        self.avoid_repeats = avoid_repeats

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
        if self.contrast_first or self.avoid_repeats:
            return self._next_pair_for_people(estimator)

        axis_name = self._pick_axis_name(estimator)
        value_a, value_b = self._most_confusable_pair(estimator, axis_name)

        combo_a = _baseline_combo(self.domain, estimator)
        combo_b = dict(combo_a)
        combo_a[axis_name] = value_a
        combo_b[axis_name] = value_b
        return combo_a, combo_b

    # --- 사람용 선택 (contrast_first / avoid_repeats) ---------------------

    def _next_pair_for_people(self, estimator: Estimator) -> Pair:
        asked = {_pair_key(c.combo_a, c.combo_b) for c in estimator.history}
        varied = {
            axis.name
            for c in estimator.history
            for axis in self._enum_axes
            if c.combo_a.get(axis.name) != c.combo_b.get(axis.name)
        }

        # 확신도 낮은 축부터. 동률은 시드 고정 RNG 로 섞는다.
        axes = list(self._enum_axes)
        self._rng.shuffle(axes)
        axes.sort(key=lambda axis: estimator.confidence(axis.name))

        first: Pair | None = None
        for axis in axes:
            for value_a, value_b in self._value_pairs(estimator, axis, varied):
                for context in self._contexts(estimator, axis.name):
                    combo_a = {**context, axis.name: value_a}
                    combo_b = {**context, axis.name: value_b}
                    if first is None:
                        first = (combo_a, combo_b)
                    if not self.avoid_repeats or _pair_key(combo_a, combo_b) not in asked:
                        return combo_a, combo_b
        # 가능한 쌍을 다 물었다. 반복은 피할 수 없으니 가장 필요한 것을 다시 묻는다.
        return first

    def _value_pairs(self, estimator: Estimator, axis, varied: set[str]) -> list[tuple[str, str]]:
        """이 축에서 물어볼 값 쌍을 우선순위대로. 효용이 낮은 값이 A 쪽."""
        utilities = estimator.utilities[axis.name]
        values = [v.value for v in axis.values]
        pairs = sorted(
            itertools.combinations(values, 2),
            key=lambda p: abs(utilities[p[0]] - utilities[p[1]]),
        )
        pairs = [tuple(sorted(p, key=lambda v: utilities[v])) for p in pairs]
        if self.contrast_first and axis.name not in varied:
            ends = (values[0], values[-1])
            pairs = [ends] + [p for p in pairs if set(p) != set(ends)]
        return pairs

    def _contexts(self, estimator: Estimator, axis_name: str) -> list[Combo]:
        """질의 축 말고 나머지 축의 값 조합. 현재 최선 추정(baseline)을
        먼저, 그다음 추정에서 덜 벗어난 순서로."""
        baseline = _baseline_combo(self.domain, estimator)
        others = [axis for axis in self._enum_axes if axis.name != axis_name]
        if not self.avoid_repeats or not others:
            return [baseline]

        choices = [
            sorted((v.value for v in axis.values), key=lambda v: v != baseline[axis.name])
            for axis in others
        ]
        contexts = []
        for values in itertools.product(*choices):
            context = dict(baseline)
            context.update({axis.name: value for axis, value in zip(others, values)})
            contexts.append(context)
        contexts.sort(key=lambda c: sum(c[a.name] != baseline[a.name] for a in others))
        return contexts
