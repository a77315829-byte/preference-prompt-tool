"""외부 리뷰(2026-10-06)가 짚은 결함의 회귀 테스트. 실제 API 는 부르지 않는다.

1. GEPA 후보 평가가 생성 캐시를 거치지 않았다 (같은 평가를 두 번 샀다).
3. 팀 1:1 의견 충돌이 "아무도 정하지 않음"으로 표시됐다.
   3-1. 값이 3개인 축에서는 1:1 로 정확히 갈려도 정의상 첫 값이 팀 값이 되어 팀 프롬프트에
   들어갔다 (3 의 테스트는 값이 2개인 coding 으로만 쟀다).
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


# --- 3-1. 값이 3개인 축의 1위 동률 --------------------------------------------------
# summarization 의 length 는 short / normal / long 이다. 1:1 로 갈리면 1위 둘은 같고 아무도 고르지
# 않은 long 만 낮다. "값들 사이에 차이가 있다"로 판정하면 신호가 있는 것으로 보여 정의상 앞인
# short 가 팀 값이 됐다.

SUMMARY = "domains/summarization.yaml"
LENGTH = "length"


def _summary_history(winner: str, strength: int = 1):
    """length 만 다른 질문들로 winner 를 고른 기록. 다른 축은 정의상 첫 값으로 고정한다."""
    domain = load_domain(SUMMARY)
    base = {axis.name: (axis.values[0].value if axis.type == "enum" else "") for axis in domain.axes}
    values = [v.value for v in domain.axis(LENGTH).values]
    history = []
    for other in values:
        if other == winner:
            continue
        a, b = dict(base, **{LENGTH: winner}), dict(base, **{LENGTH: other})
        history += [(a, b, "a")] * strength
    return history


def _length_agreement(members):
    domain = load_domain(SUMMARY)
    estimator, agreements = team.summarize(domain, members)
    prompt = service.final_prompt(domain, estimator, team=True, language="ko")
    label = domain.final_prompt.axis_labels[LENGTH]
    return next(a for a in agreements if a.axis == LENGTH), [line for line in prompt.splitlines()
                                                             if line.startswith(f"- {label}:")]


def test_even_split_on_a_three_value_axis_is_a_tie() -> None:
    agreement, lines = _length_agreement(
        [team.Member("A", _summary_history("short")), team.Member("B", _summary_history("normal"))]
    )
    assert agreement.votes == {"short": 1, "normal": 1}
    assert agreement.tied and not agreement.undecided
    assert agreement.team_value == ""  # long 이 낮다고 short 를 고른 것이 되지 않는다
    assert lines == []  # 팀 프롬프트에서 빠진다


def test_even_split_does_not_depend_on_member_order() -> None:
    # 3:3 이면 합친 효용의 차이가 부동소수점 끝자리(±4e-16)만큼 생기고 부호가 팀원 순서를 따랐다.
    people = [team.Member(f"s{i}", _summary_history("short")) for i in range(3)] + [
        team.Member(f"n{i}", _summary_history("normal")) for i in range(3)
    ]
    for members in (people, list(reversed(people))):
        agreement, lines = _length_agreement(members)
        assert agreement.tied and agreement.team_value == "" and lines == []


def _one_pick(winner: str, loser: str):
    domain = load_domain(SUMMARY)
    base = {axis.name: (axis.values[0].value if axis.type == "enum" else "") for axis in domain.axes}
    return [(dict(base, **{LENGTH: winner}), dict(base, **{LENGTH: loser}), "a")]


def test_symmetric_three_way_split_is_a_tie() -> None:
    # 가위바위보처럼 맞물린 세 사람: 각자 한 번씩, 1위·꼴찌·남은 값의 자리가 서로 돌아간다.
    # (각자 나머지 둘을 차례로 이기게 하면 두 번째 비교의 갱신 폭이 달라 대칭이 아니다 -
    # 그때는 실제로 한쪽이 조금 기운 것이라 팀 값이 정해지는 게 맞다.)
    agreement, lines = _length_agreement([
        team.Member("A", _one_pick("short", "normal")),
        team.Member("B", _one_pick("normal", "long")),
        team.Member("C", _one_pick("long", "short")),
    ])
    assert agreement.votes == {"short": 1, "normal": 1, "long": 1}
    assert agreement.tied and agreement.team_value == "" and lines == []


def test_uneven_confidence_still_leans() -> None:
    # 표는 1:1 이어도 한 사람이 더 분명하게 골랐으면 팀 값은 그쪽이다 (예전 동작 그대로).
    agreement, lines = _length_agreement(
        [team.Member("A", _summary_history("short", strength=3)), team.Member("B", _summary_history("normal"))]
    )
    assert agreement.tied and agreement.team_value == "short"
    assert len(lines) == 1


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
