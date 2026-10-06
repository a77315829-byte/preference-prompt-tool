"""외부 리뷰(2026-10-06)가 짚은 결함의 회귀 테스트. 실제 API 는 부르지 않는다.

1. GEPA 후보 평가가 생성 캐시를 거치지 않았다 (같은 평가를 두 번 샀다).
3. 팀 1:1 의견 충돌이 "아무도 정하지 않음"으로 표시됐다.
4. gepa_seed_conditions 의 부호검정이 한쪽 꼬리만 셌다 (0승 5패가 p=1).
5. 최적화할 선호가 없어 거부될 요청이 하루·세션 횟수를 먼저 깎았다.
"""

from __future__ import annotations

import json
import sys
import threading
import urllib.request
from dataclasses import replace
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

import pytest

import api_server
import service
import team
from budget import DailyBudget
from engine.domain_loader import load_domain

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "Add a counter button."


def _session(pick: str):
    state = service.start_session(SOURCE, "coding", "domains/coding.yaml", model="m", demo_mode=True)
    while not state.done:
        state = service.submit_choice(state, state.pair.pair_id, pick)
    return state


# --- 1. GEPA 평가 캐시 -------------------------------------------------------------


@pytest.fixture
def fake_litellm(monkeypatch):
    calls = []
    replies = {"text": "a summary"}

    def completion(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=replies["text"]),
                                                        finish_reason="stop")])

    monkeypatch.setitem(sys.modules, "litellm", SimpleNamespace(completion=completion))
    return calls, replies


def test_gepa_task_model_reuses_the_generation_cache(fake_litellm, tmp_path) -> None:
    calls, _ = fake_litellm
    model_fn = service.cached_task_model("m", cache_dir=tmp_path)
    messages = [{"role": "system", "content": "Summarize."}, {"role": "user", "content": SOURCE}]
    assert model_fn(messages) == "a summary"
    assert model_fn(messages) == "a summary"
    assert len(calls) == 1  # 같은 (지침, 입력)은 다시 부르지 않는다
    assert calls[0]["messages"] == messages


def test_empty_reply_scores_zero_without_being_cached(fake_litellm, tmp_path) -> None:
    calls, replies = fake_litellm
    replies["text"] = ""
    model_fn = service.cached_task_model("m", cache_dir=tmp_path)
    messages = [{"role": "system", "content": "S"}, {"role": "user", "content": "U"}]
    assert model_fn(messages) == "" and model_fn(messages) == ""
    assert len(calls) == 2  # 빈 응답은 굳히지 않는다


def _capture_adapter():
    seen = {}

    class Recorder:
        def __init__(self, model, evaluator=None, **_):
            seen["model"] = model

    def fake_optimize(seed_candidate, **_):
        return SimpleNamespace(candidates=[seed_candidate], val_aggregate_scores=[1.0])

    return seen, Recorder, fake_optimize


def test_app_optimize_hands_gepa_a_cached_function(monkeypatch) -> None:
    import gepa
    import gepa.adapters.default_adapter.default_adapter as adapter_module

    seen, recorder, fake_optimize = _capture_adapter()
    monkeypatch.setattr(adapter_module, "DefaultAdapter", recorder)
    monkeypatch.setattr(gepa, "optimize", fake_optimize)
    service.optimize(_session("a"))
    assert callable(seen["model"]) and not isinstance(seen["model"], str)


def test_experiment_gepa_also_goes_through_the_cache(monkeypatch) -> None:
    import experiments.gepa_seed_conditions as experiment

    seen, recorder, fake_optimize = _capture_adapter()
    monkeypatch.setattr(experiment, "DefaultAdapter", recorder)
    monkeypatch.setattr(experiment, "gepa_optimize", fake_optimize)
    experiment.run_gepa("seed", lambda output, source: (1.0, ""), ["a"], ["b"])
    assert callable(seen["model"]) and not isinstance(seen["model"], str)


# --- 3. 팀 1:1 의견 충돌 -----------------------------------------------------------


def test_even_split_is_a_tie_not_undecided() -> None:
    domain = load_domain("domains/coding.yaml")
    estimator, agreements = team.summarize(
        domain, [team.Member("A", _session("a").history), team.Member("B", _session("b").history)]
    )
    for a in agreements:
        assert a.tied and not a.undecided  # 표는 있다 - 갈렸을 뿐이다
        assert sum(a.votes.values()) == 2 and len(a.votes) == 2
        assert a.team_value == ""  # 정확히 반반이라 어느 쪽도 팀 값으로 삼지 않는다
    # 팀 프롬프트에서는 빠진다 (어느 쪽을 넣어도 한 사람의 선택을 지운다).
    prompt = service.final_prompt(domain, estimator, team=True, language="ko")
    for name, label in domain.final_prompt.axis_labels.items():
        assert f"- {label}:" not in prompt


def test_nobody_choosing_is_still_undecided() -> None:
    domain = load_domain("domains/coding.yaml")
    _, agreements = team.summarize(domain, [team.Member("A", _session("tie").history)])
    assert all(a.undecided and not a.tied and a.votes == {} for a in agreements)


# --- 4. 부호검정 ------------------------------------------------------------------


def test_experiment_sign_test_is_two_sided() -> None:
    from experiments.gepa_seed_conditions import sign_test_p

    assert sign_test_p(5, 5) == sign_test_p(0, 5) == 0.0625
    assert sign_test_p(4, 5) == sign_test_p(1, 5)


def test_recorded_gepa_seed_p_values_are_unchanged() -> None:
    from experiments.gepa_seed_conditions import sign_test_p

    data = json.loads((ROOT / "experiments/results/gepa_seed_conditions.json").read_text(encoding="utf-8"))
    for name, row in data["summary"].items():
        if not isinstance(row, dict) or "sign_test_p" not in row:
            continue
        wins, losses = row["rouge_wins_vs_assembled"], row["rouge_losses_vs_assembled"]
        assert sign_test_p(wins, wins + losses) == row["sign_test_p"], name


# --- 5. 거부될 최적화가 횟수를 깎지 않는다 ------------------------------------------------


def test_refused_optimisation_does_not_spend_the_caps(monkeypatch) -> None:
    monkeypatch.setattr(api_server, "DAILY_OPTIMIZATIONS", DailyBudget(3))
    state = replace(_session("tie"), demo_mode=False)  # 실제 생성 세션, 전부 비슷해요
    with api_server.SESSIONS_LOCK:
        api_server.SESSIONS[state.session_id] = state
    srv = ThreadingHTTPServer(("127.0.0.1", 0), api_server.ApiHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{srv.server_address[1]}/api/sessions/{state.session_id}/optimize",
            b"{}", {"Content-Type": "application/json"},
        )
        with pytest.raises(urllib.error.HTTPError) as err:
            urllib.request.urlopen(req)
        assert err.value.code == 400 and "정한 선호가 하나도" in json.loads(err.value.read())["error"]
        assert api_server.DAILY_OPTIMIZATIONS.left() == 3
        assert api_server.OPTIMIZE_RUNS.get(state.session_id, 0) == 0
        assert api_server.SESSIONS[state.session_id].optimize_status == "idle"
    finally:
        srv.shutdown()
        with api_server.SESSIONS_LOCK:
            api_server.SESSIONS.pop(state.session_id, None)
