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


def _question_key(combo_a: Combo, combo_b: Combo) -> tuple[str, frozenset] | None:
    """사람이 보는 질문의 식별자: 갈린 축과 그 축의 두 값 (A/B 순서 무관).
    갈린 축이 하나가 아니면 None."""
    diff = [k for k in combo_a if combo_a.get(k) != combo_b.get(k)]
    if len(diff) != 1:
        return None
    return diff[0], frozenset((combo_a[diff[0]], combo_b[diff[0]]))


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

    불확실도에 기댄 휴리스틱 질의 선택이다. 질문마다 기대 정보 이득(사후 불확실성이
    얼마나 줄지)을 계산하는 방식이 아니므로 "최적 질문 선택"이라고 부르지 않는다.

    사람을 상대하는 화면을 위한 선택 사항이 두 개 있다. 둘 다 기본은 꺼져
    있고, 꺼져 있으면 동작이 예전과 똑같다 - 실험 결과(experiments/results)
    는 이 기본 동작으로 낸 것이다.

    - contrast_first: 아직 한 번도 갈라 본 적 없는 축은 양 끝 값(YAML 의
      첫 값과 마지막 값)부터 묻는다. 처음에는 모든 효용이 0이라 "가장
      헷갈리는 쌍"이 곧 이웃한 두 값이 되고, 사람 눈에는 A/B 가 거의 같아
      보인다 (요약의 normal 대 high 추출성).
    - avoid_repeats: 질문을 "축 하나와 그 축의 두 값"으로 보고 같은 질문은
      다시 묻지 않는다. 화면에는 묻는 축의 두 값만 보이므로, 다른 축의 값만
      바꾼 쌍도 사람에게는 같은 질문이다. 다른 축은 늘 현재 추정값으로 두고,
      항상 현재 1위 값과 도전자를 붙인다 - 이미 진 두 값끼리 붙이면 1위를
      가리는 데 아무 정보도 없다. 더 물을 질문이 없으면 None 을 돌려준다
      (값 2개짜리 축은 한 번이면 끝난다). 호출하는 쪽은 그때 멈춘다.
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

    def next_pair(self, estimator: Estimator) -> Pair | None:
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

    def max_questions(self) -> int:
        """avoid_repeats 일 때 물을 수 있는 질문 수의 상한 (축마다 값 쌍의 수)."""
        return sum(len(axis.values) * (len(axis.values) - 1) // 2 for axis in self._enum_axes)

    def _next_pair_for_people(self, estimator: Estimator) -> Pair | None:
        asked = {_question_key(c.combo_a, c.combo_b) for c in estimator.history}
        varied = {key[0] for key in asked if key is not None}

        # 확신도 낮은 축부터. 동률은 시드 고정 RNG 로 섞는다.
        axes = list(self._enum_axes)
        self._rng.shuffle(axes)
        axes.sort(key=lambda axis: estimator.confidence(axis.name))
        flip = self._rng.random() < 0.5

        baseline = _baseline_combo(self.domain, estimator)
        for axis in axes:
            for value_a, value_b in self._value_pairs(estimator, axis, varied):
                if self.avoid_repeats and (axis.name, frozenset((value_a, value_b))) in asked:
                    continue
                if flip:
                    # 1위 값이 늘 같은 쪽에 서면 위치로 고르는 버릇이 생긴다.
                    value_a, value_b = value_b, value_a
                return {**baseline, axis.name: value_a}, {**baseline, axis.name: value_b}
        return None

    def _value_pairs(self, estimator: Estimator, axis, varied: set[str]) -> list[tuple[str, str]]:
        """이 축에서 물어볼 값 쌍을 우선순위대로."""
        utilities = estimator.utilities[axis.name]
        values = [v.value for v in axis.values]
        if self.contrast_first and axis.name not in varied:
            return [(values[0], values[-1])]
        if not self.avoid_repeats:
            ordered = sorted(
                itertools.combinations(values, 2),
                key=lambda p: abs(utilities[p[0]] - utilities[p[1]]),
            )
            return [tuple(sorted(p, key=lambda v: utilities[v])) for p in ordered]
        # 현재 1위와 도전자. 1위에 가까운 값부터.
        top = estimator.preferred_value(axis.name)
        challengers = sorted(
            (v for v in values if v != top), key=lambda v: utilities[top] - utilities[v]
        )
        return [(v, top) for v in challengers]
