"""선호를 정하지 못한 축은 최종 프롬프트·팀 프롬프트·최적화 채점에서 빠진다.

재현한 결함: 코딩에서 세 질문 모두 "비슷해요"를 누르면, 효용이 모두 0 이라 정의상 첫
값이 1위가 되고, 최종 프롬프트에 "이 사용자의 선호" 세 줄이 단정적으로 들어갔다.
사용자가 하지 않은 선택을 했다고 적는 셈이다. 실험 경로(build_prompt, build_metric 기본값)는
바뀌지 않아야 한다."""

from __future__ import annotations

import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

import api_server
import service
import team
from engine.domain_loader import load_domain
from engine.estimator import Comparison, Estimator
from engine.generator import build_compact_prompt, build_prompt
from engine.metric_builder import build_metric

SOURCE = "Add a counter button."


def _session(picks):
    """picks: 질문마다 고를 것 ('a' / 'b' / 'tie'). 모자라면 'tie'."""
    state = service.start_session(SOURCE, "coding", "domains/coding.yaml", model="m", demo_mode=True)
    i = 0
    while not state.done:
        state = service.submit_choice(state, state.pair.pair_id, picks[i] if i < len(picks) else "tie")
        i += 1
    return state


def test_all_ties_leave_no_invented_preferences() -> None:
    state = _session([])
    domain, estimator = service.current_estimate(state)
    assert service.undecided_axes(estimator) == ["code_structure", "style_management", "type_detail"]
    assert all(view.estimate is None for view in state.axes)
    for language in service.prompt_languages(domain):
        prompt = service.final_prompt(domain, estimator, language=language)
        # 선호 절이 통째로 빠진다 (원본·번역판 모두).
        spec = domain.final_prompt_translations.get(language) or domain.final_prompt
        assert spec.preference_heading not in prompt
        assert service.exports_for(state, prompt, language=language)


def test_only_decided_axes_reach_the_prompt() -> None:
    state = _session(["a"])  # 첫 질문만 고르고 나머지는 비슷해요
    domain, estimator = service.current_estimate(state)
    decided = [n for n in estimator.enum_axis_names() if estimator.has_signal(n)]
    assert len(decided) == 1
    prompt = service.final_prompt(domain, estimator, language="ko")
    labels = domain.final_prompt.axis_labels
    assert f"- {labels[decided[0]]}:" in prompt
    for name in service.undecided_axes(estimator):
        assert f"- {labels[name]}:" not in prompt


def test_compact_prompt_is_unchanged_when_every_axis_is_decided() -> None:
    """후보 생성용 build_prompt 와 글자까지 같아야 한다 (예전 동작, 캐시 키)."""
    for name in ("coding", "summarization", "review", "email"):
        domain = load_domain(f"domains/{name}.yaml")
        combo = {a.name: (a.values[-1].value if a.type == "enum" else "") for a in domain.axes}
        assert build_compact_prompt(domain, combo) == build_prompt(domain, combo)


def test_metric_skips_only_what_it_is_told_to() -> None:
    domain = load_domain("domains/coding.yaml")
    estimator = Estimator(domain)  # 아무 비교도 없다 - 전부 정하지 못한 축
    output = "const Counter = () => { const [n, setN] = useState(0); return <button>{n}</button>; }"
    # 실험 경로(기본값): 예전처럼 세 축을 모두 채점한다.
    _, feedback = build_metric(domain, estimator)(output, SOURCE)
    assert "파일 구성" in feedback and "스타일 관리" in feedback and "타입 작성" in feedback
    # 뺀 축만 채점 내역에서 사라진다.
    _, feedback = build_metric(domain, estimator, skip_axes={"code_structure"})(output, SOURCE)
    assert "파일 구성" not in feedback and "스타일 관리" in feedback and "타입 작성" in feedback


def test_optimize_refuses_when_nothing_was_decided() -> None:
    with pytest.raises(ValueError, match="정한 선호가 하나도"):
        service.optimize(_session([]))


def _history(picks):
    return _session(picks).history


def test_team_members_without_a_preference_do_not_vote() -> None:
    domain = load_domain("domains/coding.yaml")
    first_axis = Estimator(domain).enum_axis_names()
    # 한 사람만 선호를 정하고, 두 사람은 전부 비슷해요.
    decided = team.Member("민수", _history(["b"]))
    members = [decided, team.Member("지은", _history([])), team.Member("현우", _history([]))]
    estimator, agreements = team.summarize(domain, members)
    by_axis = {a.axis: a for a in agreements}
    personal = team._estimator(domain, [decided.history])
    for name in first_axis:
        a = by_axis[name]
        if personal.has_signal(name):
            # 비슷해요를 고른 두 사람이 정의상 첫 값에 표를 던지지 않는다.
            assert a.votes == {personal.preferred_value(name): 1} and a.team_value == personal.preferred_value(name)
            assert not a.undecided
        else:
            assert a.undecided and a.team_value == "" and a.votes == {}
    prompt = service.final_prompt(domain, estimator, team=True, language="ko")
    labels = domain.final_prompt.axis_labels
    for name in first_axis:
        assert (f"- {labels[name]}:" in prompt) == personal.has_signal(name)


def test_api_reports_undecided_axes(monkeypatch) -> None:
    monkeypatch.setattr(api_server, "LIVE", False)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), api_server.ApiHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}/api"

    def post(path, body):
        req = urllib.request.Request(base + path, json.dumps(body).encode(), {"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())["session"]

    try:
        session = post("/sessions", {"domainKey": "coding", "sourceText": SOURCE})
        while not session["done"]:
            session = post(f"/sessions/{session['session_id']}/choices",
                           {"pairId": session["pair"]["pair_id"], "chosen": "tie"})
        assert [a["axis"] for a in session["undecided_axes"]] == ["code_structure", "style_management", "type_detail"]
        assert all(a["label"] for a in session["undecided_axes"])
    finally:
        srv.shutdown()


def test_has_signal() -> None:
    domain = load_domain("domains/coding.yaml")
    estimator = Estimator(domain)
    axis = estimator.enum_axis_names()[0]
    a, b = list(estimator.utilities[axis])
    assert not estimator.has_signal(axis)
    estimator.update(Comparison({axis: a}, {axis: b}, "tie"))
    assert not estimator.has_signal(axis)  # 같은 효용에서의 무승부는 아무것도 바꾸지 않는다
    estimator.update(Comparison({axis: a}, {axis: b}, "a"))
    assert estimator.has_signal(axis) and estimator.preferred_value(axis) == a


def test_preference_note_travels_with_the_preference_section() -> None:
    """역할 문장에 "아래 선호는 ...에서 추정한 것이다"를 두면 선호가 하나도 없을 때 그 문장만
    남는다. 출처 설명은 선호 절 머리말 바로 아래에 붙고, 선호 절과 함께 빠진다."""
    for picks, decided in ((["a", "b", "a"], True), ([], False)):
        domain, estimator = service.current_estimate(_session(picks))
        for language in service.prompt_languages(domain):
            spec = domain.final_prompt_translations.get(language) or domain.final_prompt
            prompt = service.final_prompt(domain, estimator, language=language)
            assert spec.preference_note and spec.preference_note not in spec.role
            if decided:
                assert f"## {spec.preference_heading}\n{spec.preference_note}\n- " in prompt
            else:
                assert spec.preference_note not in prompt
