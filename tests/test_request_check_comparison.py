"""experiments/request_check_comparison.py - 3차 사전등록 비교. API 를 부르지 않는다."""

import pytest

from engine import generator
from experiments import personalized_prompt_comparison as base
from experiments import request_check_comparison as rc

KW = dict(split="holdout_v3", cached_only=False, behavior=False, reviewed_outputs=False,
          model="m", repeats=3, temperature=0.7, rounds=8)


def test_dry_run_sends_nothing_and_counts_the_worst_case(monkeypatch) -> None:
    monkeypatch.setattr(generator, "_call_and_cache", lambda *a, **k: pytest.fail("called the API"))
    report = rc.run(execute=False, max_api_calls=0, **KW)
    assert report["mode"] == "dry-run"
    assert report["plan"]["tasks"] == ["notify_switch", "step_counter", "todo_add", "color_choice", "word_count"]
    assert report["plan"]["max_api_requests_worst_case"] == 5 * 3 * (1 + 2 * 4)


def test_execute_refuses_a_cap_below_the_worst_case_and_unreviewed_behavior() -> None:
    with pytest.raises(ValueError, match="at least 135"):
        rc.run(execute=True, max_api_calls=134, **KW)
    with pytest.raises(ValueError, match="reviewed-outputs"):
        rc.run(execute=False, max_api_calls=0, **{**KW, "behavior": True})


def test_request_check_adds_exactly_one_rule_line() -> None:
    prompts, _ = rc.build_prompts(base.PREREGISTERED_PROFILES[0], "x", 8)
    rb, rq = prompts["rule_based"].split("\n"), prompts["request_check"].split("\n")
    added = [line for line in rq if line not in rb]
    assert added == [f"- {rc.REQUEST_CHECK_RULE}"] and len(rq) == len(rb) + 1
    assert [line for line in rq if line != added[0]] == rb
    with pytest.raises(ValueError):
        rc.with_request_check("no heading here", "항상 지킬 것")


def test_holdout_v3_is_new_and_scripted() -> None:
    from pathlib import Path
    from benchmarks.coding_ai_quality.evaluate_trial import ENTRY
    v3 = [t["id"] for t in rc.select_tasks("holdout_v3")]
    earlier = {t["id"] for s in ("calibration", "holdout", "holdout_v2") for t in base.select_tasks(s)}
    assert not set(v3) & earlier
    script = (Path(rc.ROOT) / "benchmarks" / "coding_ai_quality" / "runtime_check.cjs").read_text()
    assert all(t in ENTRY and f"task === '{t}'" in script for t in v3)


def _row(task, condition, axes, functional, repeat=0):
    return {"task": task, "condition": condition, "profile": "p", "repeat": repeat,
            "evaluation": {"axes": {f"x{i}": {"passed": v} for i, v in enumerate(axes)}},
            "behavior": {"functional_pass": functional}}


def test_summary_applies_the_preregistered_thresholds() -> None:
    rows = []
    for i in range(10):
        rows += [_row(f"t{i}", "none", [False], True), _row(f"t{i}", "rule_based", [True], i < 4),
                 _row(f"t{i}", "request_check", [True], i < 8)]
    s = rc.summarize(rows)
    assert s["paired"]["request_check-rule_based"]["functional_diff"] == 0.4
    assert s["criteria"] == {"functional_gain": True, "style_non_inferior": True} and s["all_criteria_met"]
    assert s["rule_based_functional_drop_replicated"] is True
    # 스타일이 기준보다 더 떨어지면 기능 이득이 있어도 미충족이다.
    worse = [dict(r, evaluation={"axes": {"x0": {"passed": False}}}) if r["condition"] == "request_check" else r
             for r in rows]
    assert rc.summarize(worse)["criteria"]["style_non_inferior"] is False
