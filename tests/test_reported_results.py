"""README 에 보고된 수치가 커밋된 실험 결과와 일치하는지 검증.

왜 필요한가: 리뷰 과정에서 이미 두 번, 보고된 수치와 실제 데이터가
어긋난 적이 있다(%p 와 상대% 혼용, 표본 5개에서 평균만으로 우위 주장).
데이터는 experiments/results/ 에 커밋돼 있으니, 문서가 데이터에서
멀어지는 것을 코드로 막을 수 있다. API 도 MACSum 도 필요 없다.
"""

from __future__ import annotations

import csv
import statistics
from pathlib import Path

import pytest

RESULTS = Path(__file__).resolve().parents[1] / "experiments" / "results"


def _rows(name: str) -> list[dict]:
    path = RESULTS / name
    if not path.exists():
        pytest.skip(f"결과 파일이 없다: {name}")
    return list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))


# --- 쌍 선택 알고리즘 비교 (README 3절) ------------------------------------

def _convergence():
    rows = _rows("results.csv")
    for row in rows:
        row["round"] = int(row["round"])
        row["restored"] = int(row["restored"])
        row["n_axes"] = int(row["n_axes"])
    return rows


def test_convergence_dataset_shape() -> None:
    """5문서 x 3알고리즘 x 5시드 x 10라운드 = 750행."""
    rows = _convergence()
    assert len(rows) == 750
    assert {r["algorithm"] for r in rows} == {"random", "sequential", "uncertainty"}
    assert max(r["round"] for r in rows) == 10


@pytest.mark.parametrize(
    "algorithm, mean_restored, full_recovery",
    [
        ("random", 1.32, 0.32),
        ("sequential", 1.80, 0.80),
        ("uncertainty", 1.80, 0.80),
    ],
)
def test_reported_convergence_numbers(algorithm, mean_restored, full_recovery) -> None:
    """README 3절의 수치를 데이터에서 다시 계산해 맞춘다."""
    rows = _convergence()
    final_round = max(r["round"] for r in rows)
    final = [r for r in rows if r["algorithm"] == algorithm and r["round"] == final_round]
    assert final

    assert statistics.fmean(r["restored"] for r in final) == pytest.approx(mean_restored, abs=0.01)
    achieved = sum(1 for r in final if r["restored"] == r["n_axes"]) / len(final)
    assert achieved == pytest.approx(full_recovery, abs=0.01)


def test_uncertainty_reaches_full_recovery_and_random_never_does() -> None:
    """"질의를 고르는 것이 의미 있다"는 주장의 실체. 불확실도 방식은 어느
    라운드에서 2.0/2축에 도달하고, 무작위는 10라운드 내내 못 한다."""
    rows = _convergence()
    curves = {}
    for algorithm in ("random", "uncertainty"):
        by_round = {}
        for row in rows:
            if row["algorithm"] == algorithm:
                by_round.setdefault(row["round"], []).append(row["restored"])
        curves[algorithm] = [statistics.fmean(by_round[i]) for i in sorted(by_round)]

    assert max(curves["uncertainty"]) == pytest.approx(2.0, abs=0.01)
    assert max(curves["random"]) < 1.5, curves["random"]


# --- 비교군 A/B/D (README 2절) ---------------------------------------------

def _baselines():
    rows = _rows("baseline_comparison.csv")
    for row in rows:
        row["checks_score"] = float(row["checks_score"])
        row["independent_score"] = float(row["independent_score"])
    return rows


@pytest.mark.parametrize(
    "condition, checks, independent",
    [
        ("A_no_prompt", 0.600, 0.101),
        ("B_custom_instruction", 0.668, 0.168),
        ("D_our_tool", 0.996, 0.207),
    ],
)
def test_reported_baseline_numbers(condition, checks, independent) -> None:
    rows = [r for r in _baselines() if r["condition"] == condition]
    assert len(rows) == 5, "5문서 평균으로 보고한다"
    assert statistics.fmean(r["checks_score"] for r in rows) == pytest.approx(checks, abs=0.001)
    assert statistics.fmean(r["independent_score"] for r in rows) == pytest.approx(independent, abs=0.001)


def test_independent_metric_is_much_lower_than_the_optimised_one() -> None:
    """자체 지표만 보고하면 순환 논증이다. 독립 지표에서 절대값이 크게
    낮아지는 사실 자체를 고정해둔다 (D 기준 0.996 -> 0.207)."""
    rows = [r for r in _baselines() if r["condition"] == "D_our_tool"]
    checks = statistics.fmean(r["checks_score"] for r in rows)
    independent = statistics.fmean(r["independent_score"] for r in rows)
    assert checks > 0.9
    assert independent < 0.3


def test_paired_comparison_beats_the_mean_argument() -> None:
    """표본 5개에서 평균 차이(0.039)는 표준편차보다 작다. 그래서 README 는
    문서별 페어드 비교로 "5개 중 4개에서 D 가 B 보다 높다"를 보고한다.
    그 문장을 데이터로 지킨다."""
    rows = _baselines()
    by_doc: dict[str, dict[str, float]] = {}
    for row in rows:
        by_doc.setdefault(row["doc"], {})[row["condition"]] = row["independent_score"]

    wins = sum(
        1 for scores in by_doc.values()
        if scores["D_our_tool"] > scores["B_custom_instruction"]
    )
    assert len(by_doc) == 5
    assert wins == 4, f"D 가 이긴 문서 수가 {wins}개다. README 를 고칠 것."
