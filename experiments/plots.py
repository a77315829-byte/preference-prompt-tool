"""수렴 곡선 등 시각화. experiments/results/results.csv 를 읽어 알고리즘별
평균 복원율 곡선을 그린다 - 발표의 핵심 그래프."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False


def plot_convergence(
    csv_path: str = "experiments/results/results.csv",
    out_path: str = "experiments/results/convergence.png",
) -> None:
    df = pd.read_csv(csv_path)
    grouped = df.groupby(["algorithm", "round"])["restored"].mean().reset_index()
    n_axes = df["n_axes"].iloc[0]

    fig, ax = plt.subplots(figsize=(7, 5))
    for algo, sub in grouped.groupby("algorithm"):
        ax.plot(sub["round"], sub["restored"], marker="o", label=algo)

    ax.set_xlabel("질문 횟수 (round)")
    ax.set_ylabel(f"복원된 축 수 (최대 {n_axes})")
    ax.set_title("쌍 선택 알고리즘별 수렴 곡선")
    ax.set_ylim(0, n_axes + 0.2)
    ax.legend()
    ax.grid(alpha=0.3)

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"saved plot to {out_path}")


def plot_baseline_comparison(
    csv_path: str = "experiments/results/baseline_comparison.csv",
    out_path: str = "experiments/results/baseline_comparison.png",
) -> None:
    df = pd.read_csv(csv_path)
    labels = {"A_no_prompt": "A\n(프롬프트 없음)", "B_custom_instruction": "B\n(사용자 커스텀 지침)", "D_our_tool": "D\n(본 도구)"}
    order = ["A_no_prompt", "B_custom_instruction", "D_our_tool"]

    stats = df.groupby("condition")["score"].agg(["mean", "std"]).reindex(order)

    fig, ax = plt.subplots(figsize=(6, 5))
    ax.bar(
        [labels[c] for c in order],
        stats["mean"],
        yerr=stats["std"],
        capsize=6,
        color=["#9e9e9e", "#4c72b0", "#55a868"],
    )
    ax.set_ylabel("페르소나 축값 일치 점수 (0~1)")
    ax.set_title("비교군별 페르소나 선호 일치도")
    ax.set_ylim(0, 1.15)
    ax.grid(axis="y", alpha=0.3)

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"saved plot to {out_path}")


if __name__ == "__main__":
    plot_convergence()
    plot_baseline_comparison()
