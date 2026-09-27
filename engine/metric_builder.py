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

# 선택으로 학습하는 축이 아니라 사용자가 직접 적은 값이므로 확신도가
# 없다. 사용자가 명시한 요구라 가장 확실한 축과 같은 무게를 준다.
FREEFORM_AXIS_WEIGHT = 1.0


def build_metric(
    domain: Domain,
    estimator: Estimator,
    freeform_values: dict[str, str] | None = None,
) -> Metric:
    """freeform_values: 값이 고정되지 않은 축에 사용자가 직접 준 값
    (예: 시드 프롬프트에 넣은 것과 같은 값). 비활성 값은 채점하지 않는다.
    이걸 빼면 시드 프롬프트에만 들어가고 채점은 안 돼서, 최적화가 그
    지시를 지워도 점수가 깎이지 않는다."""
    checks_module = importlib.import_module(domain.checks_module)

    target_values = {name: estimator.preferred_value(name) for name in estimator.enum_axis_names()}
    weights = {
        name: max(estimator.confidence(name), MIN_AXIS_WEIGHT) for name in estimator.enum_axis_names()
    }
    for name, value in (freeform_values or {}).items():
        if domain.axis(name).check_for(value) is None:
            continue
        target_values[name] = value
        weights[name] = FREEFORM_AXIS_WEIGHT
    total_weight = sum(weights.values())

    def metric(output: str, source: str) -> tuple[float, str]:
        # 빈 결과물은 축 검사 전에 0점으로 처리한다. "N 이하" 꼴의 목표는
        # 0개로도 충족돼서, 선호에 따라 빈 문자열이 만점을 받는다 -
        # 최적화기가 그 방향을 찾아내면 막을 방법이 없다.
        if not (output or "").strip():
            return 0.0, "결과물이 비어 있다."

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
