"""Free benchmark plumbing: no downloaded code or model APIs are executed."""
import gzip
import json
from pathlib import Path

import pytest

from benchmarks.coding_public import run as public
from benchmarks.coding_public import evaluate_docker as execution


def test_prepared_python_examples_preserve_arithmetic_and_style_contrasts():
    result = public.audit_examples()
    assert result["examples"] == 24
    assert result["arithmetic_passed"] == result["arithmetic_checks"] == 480
    for row in result["rows"]:
        if row["axis"] == "comments":
            assert row["comment_tokens"] == int(row["value"] == "detailed")
            assert row["race_comment_by_line_075"] == (row["value"] == "detailed")
            # These are inline comments, not function docstrings.
            assert not row["race_comment_by_function"]
        if row["axis"] == "structure":
            assert row["functions"] == (2 if row["value"] == "modular" else 1)


@pytest.mark.parametrize("code", [
    "import os\ndef f(a,b):\n return a+b",
    "def f(a,b):\n return __import__('os')",
    "def f(a,b):\n return a.real",
    "def f(a,b):\n while True: pass",
    "def f(a,b):\n return f(a,b)",
    "def f(a,b):\n return a ** b",
])
def test_example_interpreter_rejects_foreign_or_unbounded_operations(code):
    with pytest.raises(ValueError):
        public.example_value(code, "f", 1, 2)


def test_static_metrics_never_execute_candidate_code(tmp_path):
    marker = tmp_path / "must-not-exist"
    code = f"from pathlib import Path\nPath({str(marker)!r}).touch()\ndef f():\n return 1"
    assert public.measure_static(code)["functions"] == 1
    assert not marker.exists()
    with pytest.raises((SyntaxError, ValueError)):
        public.measure_static("return 1")
    with pytest.raises(ValueError):
        public.measure_static("# no function")


def test_incomplete_changes_require_unambiguous_original_context():
    pair = {"axis": "output", "before": "def f(a,b):\n    return a*b+3000"}
    option = {"value": "changes", "code": "    return a*b+2500"}
    code = public.complete_example(pair, option)
    assert public.example_value(code, "f", 10000, 2) == 22500
    pair["before"] += "\ndef g():\n    return 1"
    with pytest.raises(ValueError, match="Unsupported patch"):
        public.complete_example(pair, option)


def test_cached_files_are_verified_without_network(tmp_path, monkeypatch):
    def no_network(*args, **kwargs):
        pytest.fail("Offline benchmark attempted network access")
    monkeypatch.setattr(public.urllib.request, "urlopen", no_network)
    with pytest.raises(FileNotFoundError):
        public.asset_bytes("humaneval", tmp_path)
    (tmp_path / public.ASSETS["humaneval"]["file"]).write_bytes(b"tampered")
    with pytest.raises(ValueError, match="SHA-256"):
        public.asset_bytes("humaneval", tmp_path, fetch=True)


def task(task_id="Mbpp/793"):
    return {"task_id": task_id, "prompt": '"""Return the given number."""\n',
            "canonical_solution": "def f(x):\n    return x # SECRET_REFERENCE\n",
            "entry_point": "f", "base_input": [[1]], "plus_input": {}, "atol": 0}


def test_empty_upstream_plus_inputs_are_reported_not_invented(monkeypatch):
    monkeypatch.setitem(public.ASSETS, "mbpp", {"count": 1})
    data = gzip.compress(json.dumps(task()).encode())
    rows, report = public.audit_dataset("mbpp", data)
    assert report["tasks_without_plus_inputs"] == ["Mbpp/793"]
    assert report["plus_inputs"] == 0
    assert report["functional_pass_rate"] is None
    assert rows[0]["plus_input"] == {}
    invalid = task("Mbpp/2")
    with pytest.raises(ValueError, match="validation failed"):
        public.audit_dataset("mbpp", gzip.compress(json.dumps(invalid).encode()))


def test_duplicate_task_ids_are_rejected(monkeypatch):
    monkeypatch.setitem(public.ASSETS, "mbpp", {"count": 2})
    data = gzip.compress((json.dumps(task()) + "\n" + json.dumps(task())).encode())
    with pytest.raises(ValueError, match="duplicate"):
        public.audit_dataset("mbpp", data)


def test_plan_has_balanced_conditions_and_does_not_leak_answers():
    tasks = {"mbpp": [task(f"Mbpp/{i}") for i in range(21)]}
    requests = public.request_manifest(tasks)
    assert len(requests) == 21 * 5
    assert sum(r["pilot"] for r in requests) == 10 * 5
    assert len({r["request_sha256"] for r in requests}) == 5  # Identical fixtures reuse content hashes.
    assert {r["condition"] for r in requests} == {
        "general", "essential:compact", "essential:modular", "detailed:compact", "detailed:modular"}
    assert all("SECRET_REFERENCE" not in json.dumps(r["messages"]) for r in requests)
    assert requests == public.request_manifest(tasks)
    assert len(public.profiles()) == 16


def test_cost_estimate_includes_all_calls_and_output_cap():
    requests = [{"pilot": True, "dataset": "humaneval", "input_token_budget": 1000} for _ in range(100)]
    report = public.cost_estimates(requests)["scenarios"]["pilot_20_tasks"]
    assert report["calls"] == 100
    assert report["models"]["gpt-6-luna"]["usd_if_output_cap_4096_each"] == 0.2148
    assert report["models"]["gpt-6.1-sol"]["usd_if_output_cap_4096_each"] == 4.296


def test_evalplus_summary_requires_base_and_extra_tests_to_pass():
    result = {"eval": {"HumanEval/0": [{"base_status": "pass", "plus_status": "fail"}]}}
    summary = execution.summarize_result(result, {"HumanEval/0"}, True)
    assert summary["base_passed"] == 1
    assert summary["base_and_plus_passed"] == 0
    assert summary["unexpected"]


def test_negative_controls_cannot_pass_by_timing_out():
    result = {"eval": {"HumanEval/0": [{"base_status": "timeout", "plus_status": "fail"}]}}
    assert execution.summarize_result(result, {"HumanEval/0"}, False)["unexpected"]
    result["eval"]["HumanEval/0"][0]["base_status"] = "fail"
    assert execution.summarize_result(result, {"HumanEval/0"}, False)["unexpected"] == []


def test_evalplus_summary_rejects_missing_tasks_and_duplicate_samples():
    with pytest.raises(ValueError, match="Missing"):
        execution.summarize_result({"eval": {}}, {"HumanEval/0"}, True)
    with pytest.raises(ValueError, match="Missing"):
        execution.summarize_result({"eval": {"HumanEval/0": [{}, {}]}}, {"HumanEval/0"}, True)


def test_docker_execution_has_no_network_or_api_generation_path(tmp_path):
    command = execution.container_command(tmp_path / "public-inputs", tmp_path / "results", "test-controls")
    assert "--network=none" in command and "--read-only" in command
    assert "--pull=never" in command and "--cap-drop=ALL" in command
    assert execution.IMAGE in command and "@sha256:" in execution.IMAGE
    assert command[-2:] == ["python", "/datasets/controls.py"]
    assert not any("--model" in arg or "run_codegen" in arg for arg in command)
    assert not any("EVALPLUS_TIMEOUT_PER_TASK" in arg for arg in command)
    assert any("MBPP_OVERRIDE_PATH=/datasets/MbppPlus-NoExtreme" in arg for arg in command)
    assert any("evalplus/eval/__init__.py,readonly" in arg for arg in command)
    original = execution.container_command(tmp_path, tmp_path / "results", "original", False, True)
    assert not any("evalplus/eval/__init__.py,readonly" in arg for arg in original)
    assert any("MBPP_OVERRIDE_PATH=/datasets/MbppPlus-v0.2.0" in arg for arg in original)


def test_bounded_batches_preserve_every_task_and_input(tmp_path):
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    rows = [task(f"Mbpp/{i}") for i in range(101)]
    batches = execution.prepare_batches({"mbpp": rows}, inputs, tmp_path)
    assert [len(batch["task_ids"]) for batch in batches] == [50, 50, 1]
    restored = []
    for batch in batches:
        raw = (inputs / batch["file"]).read_bytes()
        assert public.digest(raw) == batch["sha256"]
        restored.extend(map(json.loads, gzip.decompress(raw).decode().splitlines()))
        for control in ("reference", "negative"):
            samples = list(map(json.loads, (tmp_path / batch[control]).read_text(encoding="utf-8").splitlines()))
            assert [row["task_id"] for row in samples] == batch["task_ids"]
    assert restored == rows


@pytest.mark.skipif(not all((public.CACHE / item["file"]).exists() for item in public.ASSETS.values()),
                    reason="Pinned public files are optional; tests never download them")
def test_full_cached_audit_is_offline_and_preserves_unknown_outcomes(tmp_path, monkeypatch):
    def no_network(*args, **kwargs):
        pytest.fail("Offline benchmark attempted network access")
    monkeypatch.setattr(public.urllib.request, "urlopen", no_network)
    for spec in public.ASSETS.values():
        (tmp_path / spec["file"]).write_bytes((public.CACHE / spec["file"]).read_bytes())
    report = public.run(tmp_path)
    fix = public.asset_bytes("evalplus_fix", tmp_path)
    execution.verify_official_fix(fix)
    with pytest.raises(ValueError, match="more than result bookkeeping"):
        execution.verify_official_fix(fix + b"\n# unrelated change\n")
    assert report["model_api_calls"] == report["model_api_cost_usd"] == 0
    assert report["prepared_requests"] == 542 * 5
    assert len(report["race_functions_verified"]) == 7
    assert all(row["functional_pass_rate"] is None for row in report["datasets"].values())
    assert sum(report["mbpp_noextreme_audit"]["excluded_plus_inputs_by_task"].values()) == 205
    assert report["mbpp_noextreme_audit"]["plus_inputs"] == 39636
    requests = list(map(json.loads, (tmp_path / "prepared/requests.NOT_EXECUTED.jsonl").read_text(encoding="utf-8").splitlines()))
    assert sum(row["pilot"] for row in requests) == 100
