"""하이브리드 판정 계층의 정확도-비용 스윕 (CLAUDE.md v2, 우선순위 3).

균형 잡힌 평가셋(test split에서 high 전부 + normal 동수 샘플)에 대해
분류기/소형LLM/대형LLM 세 계층의 판정을 각각 한 번씩만 실제로 호출해
캐싱해두고, 라우팅 임계값 스윕은 그 결과 위에서 순수 파이썬 계산으로
돌린다 - 임계값 조합마다 API를 다시 부르지 않는다.
"""

from __future__ import annotations

import random
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from dotenv import load_dotenv

from checks.summarization_hybrid import cached_llm_tier, classifier_tier, LARGE_MODEL, SMALL_MODEL
from experiments.specificity_dataset import load_examples, train_test_split

load_dotenv()

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

# 계층별 상대 비용 가중치 (호출 1회 기준, gpt-4.1-mini 대비 gpt-4.1 대략 5배
# 단가라는 공개 가격 비율을 대략적인 척도로 씀 - 정확한 청구액이 아니라
# "계층 간 상대적 비용 차이"를 보여주기 위한 근사치다).
TIER_COST = {"classifier": 0.0, "small_llm": 1.0, "large_llm": 5.0}

N_HIGH = None  # None이면 test split의 high 전부
N_NORMAL_MATCH = True  # True면 normal도 high와 같은 수만 샘플


def build_eval_set(seed: int = 0) -> list:
    examples = load_examples()
    _, test = train_test_split(examples)

    high = [e for e in test if e.label == "high"]
    normal = [e for e in test if e.label == "normal"]

    rng = random.Random(seed)
    n_high = len(high) if N_HIGH is None else N_HIGH
    n_normal = n_high if N_NORMAL_MATCH else len(normal)

    return rng.sample(high, min(n_high, len(high))) + rng.sample(normal, min(n_normal, len(normal)))


def precompute_all_tiers(eval_set: list) -> pd.DataFrame:
    rows = []
    for i, example in enumerate(eval_set):
        classifier_label, classifier_conf = classifier_tier(example.text)
        small_label, small_conf = cached_llm_tier(example.text, example.source, SMALL_MODEL, "small_llm_src")
        large_label, large_conf = cached_llm_tier(example.text, example.source, LARGE_MODEL, "large_llm_src")

        rows.append(
            {
                "text": example.text,
                "true_label": example.label,
                "classifier_label": classifier_label,
                "classifier_conf": classifier_conf,
                "small_label": small_label,
                "small_conf": small_conf,
                "large_label": large_label,
                "large_conf": large_conf,
            }
        )
        if (i + 1) % 20 == 0:
            print(f"precomputed {i + 1}/{len(eval_set)}")

    return pd.DataFrame(rows)


def route(row, classifier_threshold: float, small_threshold: float) -> tuple[str, str]:
    if row["classifier_conf"] >= classifier_threshold:
        return row["classifier_label"], "classifier"
    if row["small_conf"] >= small_threshold:
        return row["small_label"], "small_llm"
    return row["large_label"], "large_llm"


def sweep(df: pd.DataFrame, thresholds: list[float]) -> pd.DataFrame:
    rows = []
    for classifier_t in thresholds:
        for small_t in thresholds:
            predicted, tier = zip(*df.apply(lambda r: route(r, classifier_t, small_t), axis=1))
            correct = [p == t for p, t in zip(predicted, df["true_label"])]

            # 균형정확도 (라벨 불균형 보정)
            per_label_acc = []
            for label in ("normal", "high"):
                mask = df["true_label"] == label
                if mask.sum() > 0:
                    per_label_acc.append(sum(c for c, m in zip(correct, mask) if m) / mask.sum())
            balanced_accuracy = sum(per_label_acc) / len(per_label_acc)

            avg_cost = sum(TIER_COST[t] for t in tier) / len(tier)
            large_llm_ratio = sum(1 for t in tier if t == "large_llm") / len(tier)

            rows.append(
                {
                    "classifier_threshold": classifier_t,
                    "small_threshold": small_t,
                    "balanced_accuracy": balanced_accuracy,
                    "avg_cost": avg_cost,
                    "large_llm_ratio": large_llm_ratio,
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    eval_set = build_eval_set()
    print(f"eval set size: {len(eval_set)} (high={sum(1 for e in eval_set if e.label == 'high')})")

    df = precompute_all_tiers(eval_set)
    out_dir = Path("experiments/results")
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_dir / "hybrid_judge_raw.csv", index=False)

    for tier_name, label_col, conf_col in [
        ("classifier", "classifier_label", "classifier_conf"),
        ("small_llm", "small_label", "small_conf"),
        ("large_llm", "large_label", "large_conf"),
    ]:
        correct = (df[label_col] == df["true_label"]).mean()
        print(f"[{tier_name} 단독] accuracy={correct:.3f}")

    thresholds = [round(0.5 + 0.05 * i, 2) for i in range(11)]  # 0.5 ~ 1.0
    sweep_df = sweep(df, thresholds)
    sweep_df.to_csv(out_dir / "hybrid_routing_sweep.csv", index=False)

    # 대각선(classifier_threshold == small_threshold)만 뽑아 비용-정확도 곡선을 그린다.
    diag = sweep_df[sweep_df["classifier_threshold"] == sweep_df["small_threshold"]].sort_values("avg_cost")

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(diag["avg_cost"], diag["balanced_accuracy"], marker="o")
    for _, r in diag.iterrows():
        ax.annotate(f"{r['classifier_threshold']:.2f}", (r["avg_cost"], r["balanced_accuracy"]), fontsize=8)
    ax.set_xlabel("평균 상대 비용 (계층별 가중치: 분류기=0, 소형=1, 대형=5)")
    ax.set_ylabel("균형정확도")
    ax.set_title("specificity 판정: 비용 대비 정확도 (라벨=확신도 임계값)")
    ax.grid(alpha=0.3)
    fig.savefig(out_dir / "hybrid_routing_curve.png", dpi=150, bbox_inches="tight")
    print(f"saved plot to {out_dir / 'hybrid_routing_curve.png'}")


if __name__ == "__main__":
    main()
