"""benchmarks/coding_ai_quality/rescore_saved.py 의 대조 규칙. 코드를 실행하지 않는다."""

from benchmarks.coding_ai_quality.rescore_saved import trial_differences


def _r(behavior="passed", entry=None, equivalent="passed_on_covered_scenarios"):
    side = {"typecheck": True, "build": True, "behavior": behavior, "checks": [True], "entry": entry}
    return {"task": "t", "a": dict(side), "b": dict(side), "equivalent": equivalent}


def test_later_added_fields_are_ignored_but_outcomes_are_compared() -> None:
    assert trial_differences([_r(entry=None)], [_r(entry="Counter.tsx")]) == []
    assert trial_differences([_r()], [_r(behavior="failed")]) == ["t a.behavior", "t b.behavior"]
    assert trial_differences([_r()], [_r(equivalent="not_established")]) == ["t equivalent"]
    assert trial_differences([_r()], []) == ["result count 1 -> 0"]
