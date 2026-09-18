"""Regression checks for reviewed UI and optimization controls; no paid API calls."""
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

import service
from optimize.run_gepa import build_seed_prompt

APP = Path(__file__).resolve().parents[1] / "app.py"


@pytest.fixture(autouse=True)
def isolate_cached_budgets():
    st.cache_resource.clear()
    yield
    st.cache_resource.clear()


def finished_api_app(monkeypatch):
    monkeypatch.setattr(service, "generate_all", lambda *a, **k: ["Candidate A", "Candidate B"])
    original = service.start_session
    def start(*args, **kwargs):
        return original(*args, **kwargs, total_rounds=1)
    monkeypatch.setattr(service, "start_session", start)
    app = AppTest.from_file(APP, default_timeout=30).run()
    app.text_area[0].input("Create a counter button.").run()
    app.button(key="start").click().run()
    app.button(key="pick_a").click().run()
    assert not app.exception
    assert app.session_state["stage"] == "done"
    return app


def test_failed_optimization_is_limited_and_reset_keeps_quota(monkeypatch):
    calls = []
    def fail(*args, **kwargs):
        calls.append(1)
        raise RuntimeError("simulated failure")
    monkeypatch.setattr(service, "optimize", fail)
    app = finished_api_app(monkeypatch)
    for _ in range(2):
        app.button(key="optimize").click().run()
        assert not app.exception
    assert len(calls) == 2
    assert app.button(key="optimize").disabled
    assert app.session_state["optimizations_used"] == 2
    app.session_state["optimize_changed"] = True
    next(b for b in app.button if b.label == "처음부터 다시").click().run()
    assert app.session_state["stage"] == "input"
    assert app.session_state["optimizations_used"] == 2
    assert "session" not in app.session_state
    assert "optimize_changed" not in app.session_state


def test_daily_optimization_limit_blocks_call(monkeypatch):
    import budget
    original = budget.DailyBudget
    monkeypatch.setattr(budget, "DailyBudget", lambda limit: original(0 if limit == 30 else limit))
    def forbidden(*args, **kwargs):
        pytest.fail("optimization called despite exhausted daily budget")
    monkeypatch.setattr(service, "optimize", forbidden)
    app = finished_api_app(monkeypatch)
    assert app.button(key="optimize").disabled


def test_unchanged_prompt_does_not_claim_perfect_score(monkeypatch):
    def unchanged(state, **kwargs):
        domain, estimator, _ = service._rebuild(state)
        return build_seed_prompt(domain, estimator)
    monkeypatch.setattr(service, "optimize", unchanged)
    app = finished_api_app(monkeypatch)
    before = app.code[0].value
    app.button(key="optimize").click().run()
    assert not app.exception
    assert app.code[0].value == before
    assert app.session_state["optimize_changed"] is False
    captions = " ".join(c.value for c in app.caption)
    assert "이미 평가 기준을 만점으로 통과" not in captions
    assert "최적성을 뜻하지는 않습니다" in captions


def test_expert_input_discloses_server_processing(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("expert input must not call candidate generation")
    monkeypatch.setattr(service, "generate_all", forbidden)
    app = AppTest.from_file(APP, default_timeout=30).run()
    app.radio(key="build_path").set_value("내가 쓴 글에서 만들기 (자료 필요)").run()
    captions = " ".join(c.value for c in app.caption)
    assert "Streamlit 서버로 전송" in captions
    assert "브라우저 세션 안에서만" not in captions
    assert "영어 Q&A" in captions
