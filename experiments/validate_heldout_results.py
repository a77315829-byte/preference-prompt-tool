"""커밋된 CSV에서 집계를 재계산한다. 모델 호출·MACSum 원문은 필요 없다.

python -m experiments.validate_heldout_results --csv <파일> --summary <파일> [--gate <파일>]
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path

import pandas as pd

from experiments.result_statistics import (CONDITIONS, COMPARISONS, FAIR_BPLUS, FAIR_COMPARISONS,
                                          summarize, HUMAN, TOLERANCE, N_DOCS, evaluate_gate)


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _match(actual, expected, label):
    if isinstance(expected, dict):
        _require(isinstance(actual, dict) and actual.keys() == expected.keys(), f"{label}: 항목 불일치")
        for key, value in expected.items():
            _match(actual[key], value, f"{label}.{key}")
    elif isinstance(expected, float):
        _require(type(actual) in (int, float) and math.isfinite(actual)
                 and math.isclose(actual, expected, abs_tol=1e-7, rel_tol=0), f"{label}: 수치 불일치")
    elif isinstance(expected, bool):
        _require(type(actual) is bool and actual == expected, f"{label}: 불리언 불일치")
    else:
        _require(actual == expected, f"{label}: 값 불일치")


def validate_gate(path: Path) -> dict:
    gate = json.loads(Path(path).read_text(encoding="utf-8"))
    _match(gate["human_median"], HUMAN, "human_median")
    _match(gate["tolerance"], TOLERANCE, "tolerance")
    _match(gate["n_docs"], N_DOCS, "n_docs")
    _require(set(gate["median_ratio"]) == {"v1", "v2", "v3"}, "관문 조건 불일치")
    for name, medians in gate["median_ratio"].items():
        _require(set(medians) == set(HUMAN), f"{name}: 길이 값 불일치")
        _require(all(isinstance(v, (int, float)) and math.isfinite(v) and v >= 0
                     for v in medians.values()), f"{name}: 잘못된 비율")
    _match(gate["gate"], evaluate_gate(gate["median_ratio"]["v3"], HUMAN, TOLERANCE), "gate")
    if "ratio_samples" in gate:
        _require(len(gate.get("learn_docs", [])) == N_DOCS
                 and len(set(gate["learn_docs"])) == N_DOCS, "learn_docs: 표본 문서 누락/중복")
        samples = gate["ratio_samples"]
        _require(set(samples) == set(gate["median_ratio"]), "ratio_samples: 조건 불일치")
        for name, values in samples.items():
            _require(set(values) == set(HUMAN), "ratio_samples: 길이 값 불일치")
            for axis, ratios in values.items():
                _require(len(ratios) == gate["n_docs"] and all(math.isfinite(v) and v >= 0 for v in ratios),
                         "ratio_samples: 표본 수 또는 비율 오류")
                _match(gate["median_ratio"][name][axis], round(statistics.median(ratios), 4), "median_ratio")
    return {"passed": gate["gate"]["passed"], "raw_samples_available": "ratio_samples" in gate}


def validate_result_files(csv_path: Path, summary_path: Path, gate_path: Path | None = None) -> dict:
    df = pd.read_csv(csv_path)
    summary = json.loads(Path(summary_path).read_text(encoding="utf-8"))
    required = {"persona", "condition", "length", "extractiveness", "learn_doc", "eval_doc",
                "learned_exact", "checks_score", "rouge_l", "length_ratio"}
    _require(required <= set(df.columns) and len(df) > 0, "CSV: 필수 열 또는 행 누락")
    _require(not df.isna().any().any(), "CSV: 누락 값")
    _require(not df.duplicated(["persona", "condition"]).any(), "CSV: 중복 조건")
    fair = FAIR_BPLUS in set(df.condition)
    conditions = CONDITIONS + ((FAIR_BPLUS,) if fair else ())
    comparisons = COMPARISONS + (FAIR_COMPARISONS if fair else ())
    _require(all(set(group.condition) == set(conditions) for _, group in df.groupby("persona")),
             "CSV: 페르소나별 조건 누락/추가")
    for metric in ("checks_score", "rouge_l", "length_ratio"):
        _require(pd.api.types.is_numeric_dtype(df[metric]) and df[metric].map(math.isfinite).all()
                 and (df[metric] >= 0).all(), f"{metric}: 비정상 수치")
        if metric != "length_ratio":
            _require((df[metric] <= 1).all(), f"{metric}: 범위 초과")
    _require(pd.api.types.is_bool_dtype(df.learned_exact), "learned_exact: True/False 값 필요")
    stable = [c for c in df if c not in {"condition", "checks_score", "rouge_l", "length_ratio"}]
    _require((df.groupby("persona")[stable].nunique() == 1).all().all(), "CSV: 조건 사이 사례 정보 불일치")
    cases = df.drop_duplicates("persona")
    docs = list(cases.learn_doc) + list(cases.eval_doc)
    _require(len(set(docs)) == len(docs), "CSV: 학습/평가 문서 중복")
    calculated = summarize(df, conditions, comparisons)
    for key, value in calculated.items():
        _match(summary.get(key), value, key)
    _match(summary["learned_exact_rate"], round(float(cases.learned_exact.mean()), 4), "learned_exact_rate")
    for key, value in {"conditions": list(conditions), "comparisons": [list(p) for p in comparisons],
                       "fair_bplus": fair}.items():
        if key in summary:
            _match(summary[key], value, key)
    learned_axes = [c.removeprefix("learned_") for c in cases if c.startswith("learned_") and c != "learned_exact"]
    if learned_axes:
        _require(all(axis in cases for axis in learned_axes), "학습 축의 정답 열 누락")
        exact = pd.Series(True, index=cases.index)
        accuracy = {}
        for axis in learned_axes:
            correct = cases[f"learned_{axis}"] == cases[axis]
            exact &= correct
            accuracy[axis] = {"correct": int(correct.sum()), "n": len(cases)}
        _require((exact == cases.learned_exact).all(), "learned_exact: 축별 값과 불일치")
        _match(summary.get("axis_learning_accuracy"), accuracy, "axis_learning_accuracy")
    for key in ("oracle_ties", "oracle_comparisons"):
        if key in cases:
            _require(pd.api.types.is_integer_dtype(cases[key]) and (cases[key] >= 0).all(), f"{key}: 잘못된 횟수")
            _match(summary.get(key), int(cases[key].sum()), key)
    if "oracle_ties" in cases and "oracle_comparisons" in cases:
        _require((cases.oracle_ties <= cases.oracle_comparisons).all(), "동점이 비교 횟수 초과")
        if "n_rounds" in summary:
            _require((cases.oracle_comparisons == summary["n_rounds"]).all(), "비교 횟수와 n_rounds 불일치")
    if "primary_comparison" in summary:
        _require(fair, "주 비교에 필요한 B+ 조건 누락")
        result = calculated["paired"][f"rouge_l: D_our_tool vs {FAIR_BPLUS}"]
        _match(summary["primary_comparison"], {
            "metric": "rouge_l", "a": "D_our_tool", "b": FAIR_BPLUS, "alpha": 0.05,
            "test": "two-sided exact sign test, ties omitted",
            "conclusion": "D_superiority_observed" if result["wins"] > result["losses"]
                          and result["sign_test_p"] < 0.05 else "D_superiority_not_established",
            "equivalence_tested": False}, "primary_comparison")
    report = {"model": summary["model"], "n": len(cases), "conditions": list(conditions),
              "target_counts": {axis: {str(k): int(v) for k, v in cases[axis].value_counts().items()}
                                for axis in ("length", "extractiveness")},
              "axis_diagnostics_available": bool(learned_axes)}
    if gate_path is not None:
        gate = json.loads(Path(gate_path).read_text(encoding="utf-8"))
        _match(gate["model"], summary["model"], "관문/본 실험 모델")
        report["gate"] = validate_gate(gate_path)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--summary", required=True, type=Path)
    parser.add_argument("--gate", type=Path)
    args = parser.parse_args()
    try:
        result = validate_result_files(args.csv, args.summary, args.gate)
    except (ValueError, KeyError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
