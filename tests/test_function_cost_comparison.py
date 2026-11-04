"""experiments/function_cost_comparison.py - 4차 사전등록. API 를 부르지 않는다."""

import json

import pytest

from engine import generator
from experiments import function_cost_comparison as fc
from experiments import personalized_prompt_comparison as base

KW = dict(cached_only=False, behavior=False, reviewed_outputs=False, model="m", temperature=0.7, rounds=8)


def test_dry_runs_send_nothing_and_count_the_worst_case(monkeypatch) -> None:
    monkeypatch.setattr(generator, "_call_and_cache", lambda *a, **k: pytest.fail("called the API"))
    select = fc.run(phase="select", execute=False, max_api_calls=0, **KW)["plan"]
    assert len(select["tasks"]) == 8 and select["repeats"] == [0]
    assert select["max_api_requests_worst_case"] == 8 * 1 * (1 + 4) == 40
    assert fc.worst_case(5, 4, 3, fc.PHASE_CONDITIONS["confirm"]) == 5 * 3 * (2 + 4) == 90


def test_execute_needs_a_cap_and_confirm_needs_an_adequate_selection(tmp_path, monkeypatch) -> None:
    with pytest.raises(ValueError, match="at least 40"):
        fc.run(phase="select", execute=True, max_api_calls=39, **KW)
    with pytest.raises(ValueError, match="tasks-from"):
        fc.run(phase="confirm", execute=False, max_api_calls=0, **KW)
    monkeypatch.setattr(fc, "RESULTS", tmp_path)
    (tmp_path / "sel.json").write_text(json.dumps({"selection": {"enough": False, "chosen": ["page_list"]}}))
    with pytest.raises(ValueError, match="too few"):
        fc.run(phase="confirm", execute=False, max_api_calls=0, tasks_from="sel", **KW)
    (tmp_path / "sel.json").write_text(json.dumps({"selection": {"enough": True, "chosen": ["tip_calc", "page_list"]}}))
    plan = fc.run(phase="confirm", execute=False, max_api_calls=0, tasks_from="sel", **KW)["plan"]
    assert plan["tasks"] == ["page_list", "tip_calc"] and plan["repeats"] == [1, 2, 3]


def test_scaffold_only_drops_exactly_the_preference_section() -> None:
    prompts, _ = fc.build_prompts(base.PREREGISTERED_PROFILES[0], "x", 8)
    rb, sc = prompts["rule_based"], prompts["scaffold_only"]
    assert "## 이 사용자의 선호" in rb and "## 이 사용자의 선호" not in sc
    assert "- 코드 구성:" not in sc and "## 항상 지킬 것" in sc and sc.startswith(rb.split("## 이 사용자의 선호")[0])
    # 프로필과 무관하게 같다.
    other, _ = fc.build_prompts(base.PREREGISTERED_PROFILES[1], "x", 8)
    assert other["scaffold_only"] == sc and other["rule_based"] != rb
    with pytest.raises(ValueError):
        fc.scaffold_only("no heading", "이 사용자의 선호")


def _row(task, condition, profile, passed, repeat=0):
    return {"task": task, "condition": condition, "profile": profile, "repeat": repeat,
            "evaluation": {"axes": {"x": {"passed": True}}}, "behavior": {"functional_pass": passed}}


def test_selection_counts_the_shared_none_output_once_and_applies_the_rule() -> None:
    tasks = [{"id": t} for t in ("t1", "t2", "t3", "t4")]
    profiles = ["p1", "p2", "p3", "p4"]
    rows = []
    # t1: (a) 실패 1 + (b) 4개 중 3개 통과 → 0.6 (가운데), t2: 모두 통과 1.0 (범위 밖),
    # t3: (b) 2개 통과 → 0.4, t4: (a) 통과 + (b) 3개 → 0.8
    plan = {"t1": (False, [True, True, True, False]), "t2": (True, [True] * 4),
            "t3": (False, [True, True, False, False]), "t4": (True, [True, True, True, False])}
    for task, (a, bs) in plan.items():
        for p, b in zip(profiles, bs):
            rows += [_row(task, "none", p, a), _row(task, "rule_based", p, b)]
    sel = fc.select(rows, tasks)
    assert sel["pooled_functional_pass"] == {"t1": 0.6, "t2": 1.0, "t3": 0.4, "t4": 0.8}
    assert sel["chosen"] == ["t1", "t3", "t4"] and sel["enough"] is True


def test_summary_findings_follow_the_confidence_interval() -> None:
    rows = []
    for i in range(12):
        rows += [_row(f"t{i}", "none", "p", True), _row(f"t{i}", "scaffold_only", "p", True),
                 _row(f"t{i}", "rule_based", "p", i % 2 == 0)]
    f = fc.summarize(rows)["findings"]
    assert f == {"rule_based_costs_function": True, "preference_section_costs_function": True,
                 "scaffold_costs_function": False}
