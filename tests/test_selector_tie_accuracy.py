"""experiments/selector_tie_accuracy.py - 집계가 맞는지, 저장된 결과와 보고 수치가 일치하는지.
API 는 부르지 않는다. 결과 파일이 없으면 결과 대조는 건너뛴다."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.result_statistics import sign_test_p
from experiments.selector_tie_accuracy import CELLS, OUT, summarize

ROOT = Path(__file__).resolve().parents[1]


def _cell(length_ok: bool, ext_learned: str | None) -> dict:
    axes = {"length": {"learned": "short", "correct": length_ok},
            "extractiveness": {"learned": ext_learned, "correct": ext_learned == "normal"}}
    return {"axes": axes, "exact": all(a["correct"] for a in axes.values()),
            "undecided": sum(a["learned"] is None for a in axes.values()), "ties": 1}


def test_summary_counts_exact_undecided_and_paired() -> None:
    right, undecided = _cell(True, "normal"), _cell(True, None)
    rows = [{"persona": 0, **{c: right for c in CELLS}},
            {"persona": 1, **{c: undecided for c in CELLS}, "app/record-tie": right}]
    s = summarize(rows)
    assert s["cells"]["app/record-tie"]["exact"] == 2
    assert s["cells"]["app/legacy-a"]["exact"] == 1
    assert s["cells"]["app/legacy-a"]["undecided_axes"] == 1
    primary = s["primary_app_record_tie_vs_legacy"]
    assert (primary["only_app/record-tie"], primary["only_app/legacy-a"]) == (1, 0)
    assert primary["sign_test_p"] == round(sign_test_p(1, 1), 4)


def test_recorded_results_match_summary_and_report() -> None:
    path = ROOT / OUT
    if not path.exists():
        pytest.skip("결과 파일이 없다")
    data = json.loads(path.read_text(encoding="utf-8"))
    s = data["summary"]
    assert s == summarize(data["rows"])
    # 결과 문서와 README 에 적은 수치.
    assert {c: s["cells"][c]["exact"] for c in CELLS} == {
        "default/legacy-a": 19, "default/record-tie": 8, "app/legacy-a": 12, "app/record-tie": 21}
    assert s["primary_app_record_tie_vs_legacy"]["sign_test_p"] == 0.1078
