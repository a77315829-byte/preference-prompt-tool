"""experiments/personalized_prompt_comparison.py - 사전 확인은 호출 0회, 실행은 상한 안에서."""

import pytest

from experiments import personalized_prompt_comparison as comparison
from engine import generator

PROFILE = comparison.DEFAULT_PROFILE


def test_dry_run_sends_nothing(monkeypatch) -> None:
    def forbidden(*_args, **_kwargs):
        raise AssertionError("dry-run must not call the model")
    monkeypatch.setattr(generator, "_call_and_cache", forbidden)
    report = comparison.run(execute=False, task_limit=1, max_api_calls=0, model="openai/fake",
                            language="ko", profile=PROFILE, rounds=4, temperature=0.0)
    assert report["mode"] == "dry-run"
    assert report["plan"]["max_api_requests_worst_case"] == 4
    assert report["prompts"]["none"] == "" and report["prompts"]["rule_based"]


def test_execute_refuses_a_limit_below_the_worst_case(monkeypatch) -> None:
    with pytest.raises(ValueError, match="worst case"):
        comparison.run(execute=True, task_limit=2, max_api_calls=3, model="openai/fake",
                       language="ko", profile=PROFILE, rounds=4, temperature=0.0)


def test_same_output_is_recorded_as_no_difference() -> None:
    output = "```tsx\n// App.tsx\nexport const App = () => <button>ok</button>;\n```"
    evaluation = comparison.evaluate(output, "req", PROFILE)
    rows = [{"task": "t", "condition": c, "evaluation": evaluation} for c in comparison.CONDITIONS]
    notes = comparison.differences(rows)
    assert len(notes) == 3 and all("검사 통과 차이 없음" in n and "신호 수 차이 없음" in n for n in notes)
    assert set(evaluation["axes"]) == set(PROFILE)
    assert evaluation["all_passed"] is False  # 한 파일·테마 없음·타입 없음은 목표 선호와 다르다


def test_markdown_marks_skipped_ai_condition() -> None:
    report = {"generated_at": "now", "mode": "execute", "model": "m", "language": "ko", "profile": PROFILE,
              "improvement": {"method": "fallback", "reason": "api_error"},
              "usage": {"generation_requests": 2, "improvement_requests": 1, "input_tokens": 0,
                        "output_tokens": 0, "elapsed_seconds": 0},
              "note": comparison.NOTE, "differences": [],
              "rows": [{"task": "t", "condition": "ai_improved", "status": "skipped (fallback)"}]}
    text = comparison.markdown(report)
    assert "skipped (fallback)" in text and "`fallback`" in text and "청구서 아님" in text


def test_behavior_check_refuses_to_run_unreviewed_code() -> None:
    with pytest.raises(ValueError, match="reviewed-outputs"):
        comparison.run(execute=False, cached_only=True, behavior=True, task_limit=1, max_api_calls=0,
                       model="openai/fake", language="ko", profile=PROFILE, rounds=4, temperature=0.0)


def test_unextractable_or_unscripted_output_is_unknown_not_failed() -> None:
    # 코드 블록이 없으면 실행하지 못한다 - 실패로 세지 않고 미확인으로 남긴다. Node 는 돌지 않는다.
    result = comparison.behavior_check("counter_reset", "설명만 있고 코드가 없다.")
    assert result["functional_pass"] is None and result["reason"].startswith("extract_failed")
    assert comparison.behavior_check("no_such_task", "```tsx\nx\n```")["reason"] == "no_scenario"


def test_cached_only_never_calls_and_replay_needs_cached_mode(monkeypatch, tmp_path) -> None:
    def forbidden(*_args, **_kwargs):
        raise AssertionError("cached-only must not call the model")
    monkeypatch.setattr(generator, "_call_and_cache", forbidden)
    monkeypatch.setattr(comparison, "OUTPUT_DIR", tmp_path / "outputs")
    monkeypatch.setattr(comparison, "RECORD_DIR", tmp_path / "records")
    monkeypatch.setattr(generator, "generate_with_prompt",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("API request limit reached")))
    report = comparison.run(execute=False, cached_only=True, task_limit=1, max_api_calls=99,
                            model="openai/fake", language="ko", profile=PROFILE, rounds=4, temperature=0.0)
    assert report["mode"] == "cached-only" and report["usage"]["generation_requests"] == 0
    assert {row["status"] for row in report["rows"]} <= {"not_cached", "skipped (fallback)"}
    with pytest.raises(ValueError, match="cached-only"):
        comparison.run(execute=False, task_limit=1, max_api_calls=0, model="openai/fake", language="ko",
                       profile=PROFILE, rounds=4, temperature=0.0, ai_prompt_from=tmp_path / "x.json")


def test_holdout_split_collects_every_frozen_holdout_task() -> None:
    from benchmarks.coding_ai_quality.evaluate_trial import ENTRY
    holdout = [t["id"] for t in comparison.select_tasks("holdout")]
    assert holdout == ["confirm_dialog", "text_preview", "password_visibility", "faq_toggle", "cart_quantity"]
    assert all(task in ENTRY for task in holdout)  # 모두 실행 시나리오가 있다
    assert not set(holdout) & {t["id"] for t in comparison.select_tasks("calibration")}


def test_preregistered_profiles_cover_each_value_twice() -> None:
    from collections import Counter
    counts = Counter((k, v) for p in comparison.PREREGISTERED_PROFILES for k, v in p.items())
    assert len(counts) == 6 and set(counts.values()) == {2}


def _row(task, condition, passed, functional, profile="p", repeat=0):
    axes = {f"x{i}": {"passed": ok} for i, ok in enumerate(passed)}
    return {"task": task, "condition": condition, "profile": profile, "repeat": repeat,
            "evaluation": {"axes": axes, "all_passed": all(passed)},
            "behavior": {"functional_pass": functional}}


def test_summary_applies_the_preregistered_thresholds() -> None:
    rows = []
    for i in range(4):
        rows += [_row(f"t{i}", "none", [False, False, False], True),
                 _row(f"t{i}", "rule_based", [True, False, False], True),
                 _row(f"t{i}", "ai_improved", [True, True, False], True)]
    profiles = [{"improvement": {"method": "ai_improved"}}]
    summary = comparison.summarize(rows, profiles)
    gain = summary["paired"]["ai_improved-rule_based"]
    assert gain["units"] == 4 and abs(gain["axis_pass_diff"] - 1 / 3) < 1e-3
    assert summary["criteria"] == {"style_gain": True, "functional_non_inferior": True, "fallback_rate": True}
    assert summary["all_criteria_met"] is True

    # 기능이 떨어지면 스타일 이득이 있어도 기준 미충족.
    worse = [dict(r, behavior={"functional_pass": False}) if r["condition"] == "ai_improved" else r for r in rows]
    assert comparison.summarize(worse, profiles)["all_criteria_met"] is False
    # 미확인은 통과로 세지 않는다.
    unknown = [dict(r, behavior={"functional_pass": None}) if r["condition"] == "ai_improved" else r for r in rows]
    s = comparison.summarize(unknown, profiles)
    assert s["conditions"]["ai_improved"]["functional_pass_rate"] == 0.0
    assert s["conditions"]["ai_improved"]["functional_unknown"] == 4
    # 실행 검사를 안 돌렸으면 판정할 수 없다 (None).
    no_behavior = [dict(r, behavior=None) for r in rows]
    assert comparison.summarize(no_behavior, profiles)["all_criteria_met"] is None
    # 개선이 적용되지 않은 프로필이 많으면 미충족.
    assert comparison.summarize(rows, [{"improvement": {"method": "fallback"}}])["criteria"]["fallback_rate"] is False


def test_holdout_v2_tasks_are_new_and_scripted() -> None:
    """2차 사전등록의 holdout 은 1차 holdout·calibration 과 겹치지 않고 모두 실행 시나리오가 있다."""
    from pathlib import Path
    from benchmarks.coding_ai_quality.evaluate_trial import ENTRY
    v2 = [t["id"] for t in comparison.select_tasks("holdout_v2")]
    assert v2 == ["tab_switch", "char_counter", "star_rating", "like_toggle", "temperature_convert"]
    earlier = {t["id"] for split in ("calibration", "holdout") for t in comparison.select_tasks(split)}
    assert not set(v2) & earlier
    script = (Path(comparison.ROOT) / "benchmarks" / "coding_ai_quality" / "runtime_check.cjs").read_text()
    assert all(task in ENTRY and f"task === '{task}'" in script for task in v2)
    assert set(comparison.CONFIRMATORY_SPLITS) == {"holdout", "holdout_v2"}


def test_improvement_model_reaches_the_plan_and_service(monkeypatch) -> None:
    seen = {}

    def fake_complete(state, languages, **kwargs):
        from dataclasses import replace
        seen.update(kwargs)
        return replace(state, prompt_improvement={"method": "rule_based", "model": kwargs["model"]})
    monkeypatch.setattr(comparison.service, "complete_personalized_prompt", fake_complete)
    report = comparison.run(execute=False, task_limit=1, max_api_calls=0, model="m", language="ko",
                            rounds=4, temperature=None, improvement_model="strong")
    assert report["plan"]["improvement_model"] == "strong"
    history = comparison.simulate_history(PROFILE, "x", 4)
    _, meta = comparison.build_prompts(history, "m", "ko", execute=True, reserve=lambda: None,
                                       improvement_model="strong")
    assert seen["model"] == meta["model"] == "strong"
