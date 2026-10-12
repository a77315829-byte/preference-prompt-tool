"""Frozen evaluation inputs for live coding A/B generation."""

import json
from collections import Counter
from pathlib import Path

import pytest

import service
from benchmarks.coding_ai_quality.run_trial import run_trial


BENCHMARK = Path(__file__).resolve().parents[1] / "benchmarks/coding_ai_quality/v1.json"
AXIS_VALUES = {
    "code_structure": {"compact", "separated"},
    "style_management": {"direct", "theme"},
    "type_detail": {"inferred", "explicit"},
}


def test_coding_ai_benchmark_is_frozen_and_balanced() -> None:
    data = json.loads(BENCHMARK.read_text(encoding="utf-8"))
    tasks = data["tasks"]

    assert data["version"] == "1.0"
    assert data["baseline_model"] == "openai/gpt-4o-mini"
    assert data["generation_mode"] == "live"
    assert data["rounds_per_task"] == 1
    assert set(data["required_axes"]) == set(AXIS_VALUES)
    assert len(tasks) == 6
    assert len({task["id"] for task in tasks}) == len(tasks)
    assert Counter(task["axis"] for task in tasks) == {axis: 2 for axis in AXIS_VALUES}
    assert Counter(task["split"] for task in tasks) == {"calibration": 4, "holdout": 2}

    for task in tasks:
        assert task["id"] and task["request"].strip()
        assert "React" in task["request"] and "TypeScript" in task["request"]
        assert len(task["acceptance"]) >= 3
        assert len(set(task["acceptance"])) == len(task["acceptance"])
        assert all(criterion.strip() for criterion in task["acceptance"])
        assert task["axis"] in AXIS_VALUES
        assert set(task["common_profile"]) == set(AXIS_VALUES) - {task["axis"]}
        for axis, value in task["common_profile"].items():
            assert value in AXIS_VALUES[axis]


def test_coding_ai_benchmark_has_no_predeclared_model_winners() -> None:
    data = json.loads(BENCHMARK.read_text(encoding="utf-8"))
    for task in data["tasks"]:
        assert "winner" not in task
        assert "model_output" not in task
        assert "score" not in task


def test_trial_dry_run_uses_only_calibration_and_changes_one_axis() -> None:
    report = run_trial(execute=False, task_limit=4, max_api_attempts=0)
    pairs = report["planned_pairs"]

    assert len(pairs) == 8
    assert report["maximum_api_attempts_with_repairs"] == 32
    assert {pair["task"] for pair in pairs} == {
        "counter_reset", "product_search", "signup_validation", "todo_toggle"
    }
    for pair in pairs:
        differences = {axis for axis in AXIS_VALUES if pair["a"][axis] != pair["b"][axis]}
        assert len(differences) == 1
    for first, second in zip(pairs[::2], pairs[1::2]):
        assert first["task"] == second["task"]
        assert first["a"] == second["a"]
        assert first["b"] == second["b"]
        assert first["model"] != second["model"]


def test_trial_rejects_invalid_task_limit_before_any_call() -> None:
    with pytest.raises(ValueError, match="task_limit"):
        run_trial(execute=False, task_limit=5, max_api_attempts=0)


def test_trial_can_select_one_calibration_task_without_repeating_earlier_tasks() -> None:
    report = run_trial(execute=False, task_limit=4, max_api_attempts=0,
                       task_id="product_search")

    assert len(report["planned_pairs"]) == 2
    assert {pair["task"] for pair in report["planned_pairs"]} == {"product_search"}
    assert report["maximum_api_attempts_with_repairs"] == 8


def test_trial_rejects_holdout_task_selection() -> None:
    with pytest.raises(ValueError, match="Unknown calibration task"):
        run_trial(execute=False, task_limit=4, max_api_attempts=0,
                  task_id="confirm_dialog")


def test_holdout_dry_run_is_separate_and_balanced() -> None:
    report = run_trial(
        execute=False, task_limit=2, max_api_attempts=0, split="holdout",
        route_model="openai/gpt-6-luna", escalation_model="openai/gpt-6.1-sol",
    )

    assert report["split"] == "holdout"
    assert [pair["task"] for pair in report["planned_pairs"]] == [
        "confirm_dialog", "text_preview",
    ]
    assert report["maximum_api_attempts_with_repairs"] == 12
    assert all(sum(pair["a"][axis] != pair["b"][axis] for axis in AXIS_VALUES) == 1
               for pair in report["planned_pairs"])


def test_fresh_holdout_v2_uses_one_unseen_task() -> None:
    benchmark_path = BENCHMARK.with_name("v2.json")
    report = run_trial(
        execute=False, task_limit=1, max_api_attempts=0, split="holdout",
        route_model="openai/gpt-6-luna", escalation_model="openai/gpt-6.1-sol",
        benchmark_path=benchmark_path,
    )
    assert [pair["task"] for pair in report["planned_pairs"]] == ["password_visibility"]
    assert report["maximum_api_attempts_with_repairs"] == 6
    assert sum(report["planned_pairs"][0]["a"][axis] != report["planned_pairs"][0]["b"][axis]
               for axis in AXIS_VALUES) == 1


def test_fresh_holdout_v3_uses_one_unseen_faq_task() -> None:
    report = run_trial(
        execute=False, task_limit=1, max_api_attempts=0, split="holdout",
        route_model="openai/gpt-6-luna", escalation_model="openai/gpt-6.1-sol",
        benchmark_path=BENCHMARK.with_name("v3.json"),
    )
    assert [pair["task"] for pair in report["planned_pairs"]] == ["faq_toggle"]
    assert report["maximum_api_attempts_with_repairs"] == 6
    assert sum(report["planned_pairs"][0]["a"][axis] != report["planned_pairs"][0]["b"][axis]
               for axis in AXIS_VALUES) == 1


def test_holdout_rejects_calibration_task_and_extra_task_limit() -> None:
    with pytest.raises(ValueError, match="Unknown holdout task"):
        run_trial(execute=False, task_limit=2, max_api_attempts=0,
                  split="holdout", task_id="counter_reset")
    with pytest.raises(ValueError, match="task_limit"):
        run_trial(execute=False, task_limit=3, max_api_attempts=0, split="holdout")


def test_service_route_dry_run_is_one_pair_and_bounded() -> None:
    report = run_trial(
        execute=False, task_limit=1, max_api_attempts=0,
        route_model="openai/gpt-6-luna",
        escalation_model="openai/gpt-6.1-sol",
    )

    assert len(report["planned_pairs"]) == 1
    assert report["planned_pairs"][0]["model"] == "openai/gpt-6-luna"
    assert report["escalation_model"] == "openai/gpt-6.1-sol"
    assert report["maximum_api_attempts_with_repairs"] == 6


def test_service_route_passes_escalation_to_product_path_without_api_calls(
    monkeypatch, tmp_path,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-key")
    states = []

    def fake_pair(state, domain, combo_a, combo_b):
        states.append(state)
        raise service.CodingCandidateQualityError("A", ["파일 구성 위반"])

    monkeypatch.setattr(service, "_generate_pair", fake_pair)
    report = run_trial(
        execute=True, task_limit=1, max_api_attempts=6,
        output=tmp_path / "routed.json",
        route_model="openai/gpt-6-luna",
        escalation_model="openai/gpt-6.1-sol",
    )

    assert len(states) == 1
    assert states[0].model == "openai/gpt-6-luna"
    assert states[0].coding_escalation_model == "openai/gpt-6.1-sol"
    assert report["total_api_attempts"] == 0
    assert report["results"][0]["status"] == "quality_failure"


def test_service_route_rejects_insufficient_attempt_limit_before_api_call(
    monkeypatch, tmp_path,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-key")
    with pytest.raises(ValueError, match="6 calls per pair"):
        run_trial(
            execute=True, task_limit=1, max_api_attempts=5,
            output=tmp_path / "routed.json",
            route_model="openai/gpt-6-luna",
            escalation_model="openai/gpt-6.1-sol",
        )


def test_trial_records_quality_failure_reasons_without_api_calls(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-key")

    def fail_pair(*args, **kwargs):
        raise service.CodingCandidateQualityError("B", ["파일 구성 위반", "타입 작성 위반"])

    monkeypatch.setattr(service, "_generate_pair", fail_pair)
    report = run_trial(
        execute=True, task_limit=1, max_api_attempts=8,
        output=tmp_path / "trial.json",
    )

    assert len(report["results"]) == 2
    assert report["total_api_attempts"] == 0
    assert all(item["status"] == "quality_failure" for item in report["results"])
    assert all(item["failed_candidate"] == "B" for item in report["results"])
    assert all(item["failure_reasons"] == ["파일 구성 위반", "타입 작성 위반"]
               for item in report["results"])
