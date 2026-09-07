"""선호(estimator의 추정 결과) -> GEPA용 평가 함수 조립.

domain.checks_module 에 지정된 검사 함수들을 축별 확신도로 가중평균해
하나의 metric 함수로 만든다. 확신도가 낮은 축은 (아직 사용자 선호가
불확실하므로) 점수에 덜 반영되지만, 완전히 무시되지는 않도록 최소
가중치를 둔다. 자연어 피드백도 함께 반환해 GEPA의 성찰에 쓰인다.

이 모듈은 축이 N개 있고 각 축에 값이 M개 있다는 것만 알 뿐, 어떤
도메인인지는 모른다 - 실제 검사 로직은 domain.checks_module 에 위임한다.
"""

from __future__ import annotations

import importlib
from typing import Callable

from engine.domain_loader import Domain
from engine.estimator import Estimator

Metric = Callable[[str, str], tuple[float, str]]

MIN_AXIS_WEIGHT = 0.05


def build_metric(domain: Domain, estimator: Estimator) -> Metric:
    checks_module = importlib.import_module(domain.checks_module)

    target_values = {name: estimator.preferred_value(name) for name in estimator.enum_axis_names()}
    weights = {
        name: max(estimator.confidence(name), MIN_AXIS_WEIGHT) for name in estimator.enum_axis_names()
    }
    total_weight = sum(weights.values())

    def metric(output: str, source: str) -> tuple[float, str]:
        weighted_score = 0.0
        feedback_lines = []

        for axis in domain.axes:
            if axis.name not in target_values:
                continue

            value = target_values[axis.name]
            check_spec = axis.check_for(value)
            check_fn = getattr(checks_module, check_spec.fn)
            score, feedback = check_fn(output, source, value, check_spec.target)

            weighted_score += weights[axis.name] * score
            feedback_lines.append(feedback)

        overall_score = weighted_score / total_weight if total_weight else 0.0
        return overall_score, " ".join(feedback_lines)

    return metric
