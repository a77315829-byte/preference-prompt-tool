"""GEPA 연동.

estimator가 추정한 축별 선호로 seed 시스템 프롬프트를 조립하고,
metric_builder.build_metric()이 만든 metric(output, source)을 GEPA의
Evaluator 프로토콜에 맞게 감싸 gepa.optimize()를 호출한다.

설치된 gepa(0.1.4)는 CLAUDE.md 초안의 `metric=` 인자를 받지 않는다.
대신 DefaultAdapter(model, evaluator) 조합을 쓴다 - evaluator는
(data, response) -> EvaluationResult(score, feedback) 를 반환해야 하고,
DefaultAdapter는 data["input"]을 사용자 메시지로, candidate 딕셔너리의
값 하나를 시스템 프롬프트로 사용한다.
"""

from __future__ import annotations

from gepa import optimize as gepa_optimize
from gepa.adapters.default_adapter.default_adapter import DefaultAdapter, EvaluationResult
from gepa.core.result import GEPAResult

from engine.domain_loader import Domain
from engine.estimator import Estimator
from engine.generator import build_prompt
from engine.metric_builder import Metric, build_metric


class MetricEvaluator:
    """metric_builder.build_metric()의 결과를 GEPA Evaluator 프로토콜로 감싼다."""

    def __init__(self, metric: Metric) -> None:
        self.metric = metric

    def __call__(self, data: dict, response: str) -> EvaluationResult:
        score, feedback = self.metric(response, data["input"])
        return EvaluationResult(score=score, feedback=feedback)


def build_seed_prompt(domain: Domain, estimator: Estimator, topic: str = "") -> str:
    combo = {name: estimator.preferred_value(name) for name in estimator.enum_axis_names()}
    for axis in domain.axes:
        if axis.type != "enum":
            combo[axis.name] = topic if axis.name == "topic" else ""
    return build_prompt(domain, combo)


def run(
    domain: Domain,
    estimator: Estimator,
    train_sources: list[str],
    val_sources: list[str] | None = None,
    topic: str = "",
    task_lm: str = "openai/gpt-4.1-mini",
    reflection_lm: str = "openai/gpt-4.1-mini",
    max_metric_calls: int = 150,
) -> tuple[str, GEPAResult]:
    seed_prompt = build_seed_prompt(domain, estimator, topic=topic)
    metric = build_metric(domain, estimator)

    trainset = [{"input": s} for s in train_sources]
    valset = [{"input": s} for s in val_sources] if val_sources is not None else None

    adapter = DefaultAdapter(model=task_lm, evaluator=MetricEvaluator(metric))

    result = gepa_optimize(
        seed_candidate={"system_prompt": seed_prompt},
        trainset=trainset,
        valset=valset,
        adapter=adapter,
        reflection_lm=reflection_lm,
        max_metric_calls=max_metric_calls,
        display_progress_bar=True,
    )

    return result.best_candidate["system_prompt"], result
