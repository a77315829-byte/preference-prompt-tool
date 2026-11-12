"""Offline checks for paid-call accounting; no real client or network."""
import copy
import json
from types import SimpleNamespace

import pytest

from benchmarks.coding_public import pilot


def fixture_plan():
    rows = []
    for index in range(100):
        payload = {"input": str(index)}
        rows.append({"id": pilot.sha(payload), "payload": payload, "input_token_budget": 3000,
                     "reservation_nano_usd": 2_348_000, "task_id": str(index // 5), "condition": str(index % 5)})
    return {"requests": rows}


class FakeClient:
    def __init__(self, fail=False):
        self.responses = self
        self.calls = 0
        self.fail = fail

    def create(self, **kwargs):
        self.calls += 1
        if self.fail:
            raise TimeoutError("not printed")
        response = {"model": pilot.MODEL, "service_tier": "default", "status": "completed",
                    "usage": {"input_tokens": 1000, "output_tokens": 600,
                              "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0}}}
        return SimpleNamespace(model_dump=lambda **_: copy.deepcopy(response), output_text="```python\ndef f(): return 1\n```")


def output(tmp_path):
    (tmp_path / "answers").mkdir()
    return tmp_path


def test_hundred_answers_are_cached_without_duplicate_calls(tmp_path):
    path, plan, client = output(tmp_path), fixture_plan(), FakeClient()
    ledger = pilot.execute(plan, path, client)
    assert client.calls == 100
    assert pilot.committed(ledger) == 40_000_000
    pilot.execute(plan, path, client)
    assert client.calls == 100


def test_ambiguous_failure_retains_reservation_and_cannot_retry(tmp_path):
    path, plan, client = output(tmp_path), fixture_plan(), FakeClient(fail=True)
    with pytest.raises(RuntimeError, match="no retry"):
        pilot.execute(plan, path, client)
    ledger = json.loads((path / "ledger.json").read_text())
    assert pilot.committed(ledger) == plan["requests"][0]["reservation_nano_usd"]
    with pytest.raises(RuntimeError, match="automatic retry forbidden"):
        pilot.execute(plan, path, client)
    assert client.calls == 1


def test_budget_blocks_before_network(tmp_path, monkeypatch):
    path, plan, client = output(tmp_path), fixture_plan(), FakeClient()
    monkeypatch.setattr(pilot, "CAP", 1)
    with pytest.raises(RuntimeError, match="Budget"):
        pilot.execute(plan, path, client)
    assert client.calls == 0


def test_changed_plan_does_not_make_extra_call(tmp_path):
    path, plan, client = output(tmp_path), fixture_plan(), FakeClient()
    pilot.execute(plan, path, client)
    plan["new_settings"] = "changed"
    with pytest.raises(ValueError, match="Plan changed"):
        pilot.execute(plan, path, client)
    assert client.calls == 100


@pytest.mark.parametrize("field,value", [("model", "gpt-6.1-sol"), ("service_tier", "priority")])
def test_price_assumption_change_stops(tmp_path, field, value):
    response = FakeClient().create().model_dump()
    response[field] = value
    with pytest.raises(ValueError):
        pilot.charge(response, fixture_plan()["requests"][0])


def test_cache_write_or_excess_usage_stops():
    response = FakeClient().create().model_dump()
    response["usage"]["input_tokens_details"]["cache_write_tokens"] = 100
    with pytest.raises(ValueError, match="cache"):
        pilot.charge(response, fixture_plan()["requests"][0])
    response["usage"]["input_tokens_details"]["cache_write_tokens"] = 0
    response["usage"]["output_tokens"] = 4097
    with pytest.raises(ValueError, match="allowance"):
        pilot.charge(response, fixture_plan()["requests"][0])


def test_transient_windows_rename_retries_only_disk_write(tmp_path, monkeypatch):
    original = type(tmp_path).replace
    attempts = []

    def briefly_locked(path, target):
        attempts.append(path)
        if len(attempts) == 1:
            raise PermissionError("file briefly locked")
        return original(path, target)

    monkeypatch.setattr(type(tmp_path), "replace", briefly_locked)
    monkeypatch.setattr(pilot.time, "sleep", lambda _: None)
    pilot.save(tmp_path / "state.json", {"ok": True})
    assert json.loads((tmp_path / "state.json").read_text()) == {"ok": True}
    assert len(attempts) == 2


def test_generated_code_is_parsed_and_screened_without_running():
    from benchmarks.coding_public.pilot_evaluate import inspect_answer

    code, result = inspect_answer("```python\ndef f(x):\n    # a comment\n    return x + 1\n```", "f", "completed")
    assert result["valid"] and result["comment_tokens"] == 1
    assert code.startswith("def f")
    for text, status in [("```python\nimport os\ndef f(): return os.getcwd()\n```", "completed"),
                         ("```python\ndef f(): return open('secret')\n```", "completed"),
                         ("```python\ndef f(): return 1\n```", "incomplete"),
                         ("```python\ndef wrong(): return 1\n```", "completed"),
                         ("No code", "completed")]:
        code, result = inspect_answer(text, "f", status)
        assert code is None and not result["valid"]


def test_usage_example_is_separate_from_strict_format_score():
    from benchmarks.coding_public.pilot_evaluate import inspect_answer

    text = "```python\nimport cmath\ndef f(): return cmath.phase(1j)\n```\n\n```python\nprint(f())\n```"
    code, result = inspect_answer(text, "f", "completed")
    assert result["valid"] and not result["single_code_block"]
    assert "print" not in code
    ambiguous = text + "\n```python\ndef f(): return 5\n```"
    code, result = inspect_answer(ambiguous, "f", "completed")
    assert code is None and not result["valid"]
