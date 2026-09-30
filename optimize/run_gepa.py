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


def _freeform_values(domain: Domain, topic: str) -> dict[str, str]:
    return {
        axis.name: (topic if axis.name == "topic" else "")
        for axis in domain.axes
        if axis.type != "enum"
    }


def build_seed_prompt(domain: Domain, estimator: Estimator, topic: str = "") -> str:
    combo = {name: estimator.preferred_value(name) for name in estimator.enum_axis_names()}
    combo.update(_freeform_values(domain, topic))
    return build_prompt(domain, combo)


def run(
    domain: Domain,
    estimator: Estimator,
    train_sources: list[str],
    val_sources: list[str] | None = None,
    topic: str = "",
    # 이 함수는 실제 제품 경로(app.py, api_server.py)에서 쓰이지 않는다 -
    # 둘 다 service.optimize() 를 직접 부른다. 실험·테스트 전용 진입점이라
    # 기본값이 안 맞아도 아무도 모르게 지나갈 수 있으므로 제품과 같게 둔다:
    # 후보 생성은 app.py 의 MODEL, 성찰은 service.REFLECTION_MODEL 의 기본값.
    # (service 를 import 하면 순환이라 문자열로 적는다.)
    task_lm: str = "openai/gpt-4o-mini",
    reflection_lm: str = "openai/gpt-5.6-luna",
    max_metric_calls: int = 150,
) -> tuple[str, GEPAResult]:
    seed_prompt = build_seed_prompt(domain, estimator, topic=topic)
    # 시드에 넣은 자유 키워드 값을 채점에도 넣는다. 안 넣으면 GEPA 가
    # 주제 지시를 지운 프롬프트를 골라도 점수가 그대로다.
    metric = build_metric(domain, estimator, freeform_values=_freeform_values(domain, topic))

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
