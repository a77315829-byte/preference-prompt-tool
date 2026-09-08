"""GEPA 피드백 풍부도 어블레이션 (CLAUDE.md v2, 보너스 실험).

metric_builder.py가 만드는 축별 자연어 피드백("길이 위반: 6문장 (목표
2문장 이하). 추출성 위반: ...")이 GEPA의 성찰(reflection)에 실제로 도움이
되는지 검증한다. 점수 계산 로직은 완전히 동일하게 두고 GEPA에게 보이는
피드백 텍스트만 "rich"(현재 구현, 축별 위반 내역)와 "terse"(점수만)로
바꿔서, 같은 호출 예산 안에서 도달하는 점수를 비교한다.

"우리는 축을 명시적으로 갖고 있어서 구조화된 피드백을 줄 수 있다"는
프로젝트의 기여 주장에 대한 직접적인 실증이다.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
from dotenv import load_dotenv
from gepa import optimize as gepa_optimize
from gepa.adapters.default_adapter.default_adapter import DefaultAdapter

from engine.domain_loader import load_domain
from engine.estimator import Comparison, Estimator
from engine.metric_builder import Metric, build_metric
from optimize.run_gepa import MetricEvaluator, build_seed_prompt

load_dotenv()

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

TASK_LM = "openai/gpt-4.1-mini"
REFLECTION_LM = "openai/gpt-4.1-mini"
MAX_METRIC_CALLS = 40  # 두 조건 동일 예산
SEED = 0


def make_terse_metric(rich_metric: Metric) -> Metric:
    def terse(output: str, source: str) -> tuple[float, str]:
        score, _ = rich_metric(output, source)
        return score, f"Score: {score:.2f}"

    return terse


def run_once(seed_prompt: str, metric: Metric, train_sources: list[str], val_sources: list[str]):
    adapter = DefaultAdapter(model=TASK_LM, evaluator=MetricEvaluator(metric))
    trainset = [{"input": s} for s in train_sources]
    valset = [{"input": s} for s in val_sources]

    return gepa_optimize(
        seed_candidate={"system_prompt": seed_prompt},
        trainset=trainset,
        valset=valset,
        adapter=adapter,
        reflection_lm=REFLECTION_LM,
        max_metric_calls=MAX_METRIC_CALLS,
        seed=SEED,
        display_progress_bar=False,
    )


def running_best(discovery_counts: list[int], scores: list[float]) -> tuple[list[int], list[float]]:
    order = sorted(range(len(discovery_counts)), key=lambda i: discovery_counts[i])
    xs, ys, best = [], [], float("-inf")
    for i in order:
        best = max(best, scores[i])
        xs.append(discovery_counts[i])
        ys.append(best)
    return xs, ys


def main() -> None:
    domain = load_domain("domains/summarization.yaml")

    estimator = Estimator(domain)
    for _ in range(20):
        estimator.update(
            Comparison(
                {"length": "short", "extractiveness": "fully", "topic": ""},
                {"length": "long", "extractiveness": "normal", "topic": ""},
                "a",
            )
        )

    # 일부러 못 맞는 시드를 쓴다 - build_seed_prompt()로 만든 시드는 이미
    # metric에 최적화돼 있어(당연히, 같은 선호에서 나왔으므로) val 점수가
    # 처음부터 1.0으로 포화돼 두 조건의 차이가 드러날 여지가 없었다
    # (1차 실행에서 확인). GEPA가 실제로 개선할 여지가 있어야 피드백
    # 풍부도의 효과를 비교할 수 있다.
    seed_prompt = "Summarize the following text."
    rich_metric = build_metric(domain, estimator)
    terse_metric = make_terse_metric(rich_metric)

    records = json.loads(Path("data/macsum/dataset/macdoc/val.json").read_text(encoding="utf-8"))
    sources = [" ".join(r["source"]) for r in records[:6]]
    train_sources, val_sources = sources[:4], sources[4:6]

    curves = {}
    finals = {}
    for name, metric in [("rich (축별 피드백)", rich_metric), ("terse (점수만)", terse_metric)]:
        print(f"=== running: {name} ===")
        result = run_once(seed_prompt, metric, train_sources, val_sources)
        xs, ys = running_best(result.discovery_eval_counts, result.val_aggregate_scores)
        curves[name] = (xs, ys)
        finals[name] = result.val_aggregate_scores[result.best_idx]
        print(f"{name}: best val score = {finals[name]:.3f} (candidates explored: {result.num_candidates})")

    fig, ax = plt.subplots(figsize=(7, 5))
    for name, (xs, ys) in curves.items():
        ax.step(xs, ys, where="post", marker="o", label=name)
    ax.set_xlabel("누적 metric 호출 수")
    ax.set_ylabel("지금까지 최고 검증 점수")
    ax.set_title("GEPA 피드백 풍부도에 따른 수렴 속도")
    ax.legend()
    ax.grid(alpha=0.3)

    out_path = Path("experiments/results/feedback_richness_ablation.png")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"saved plot to {out_path}")
    print("finals:", finals)


if __name__ == "__main__":
    main()
