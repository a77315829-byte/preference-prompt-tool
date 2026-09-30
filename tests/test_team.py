"""팀 모드 검증. API 호출은 없다 (데모 세션)."""

import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

import api_server
import service
import team
from engine.domain_loader import load_domain

SECRET_SOURCE = "Internal roadmap: project Nightingale ships in March."


def _history(domain_file: str, prefer: dict[str, str]):
    """prefer 에 적힌 값을 늘 고르는 사람의 선택 기록."""
    state = service.start_session(SECRET_SOURCE, domain_file, f"domains/{domain_file}.yaml",
                                  model="m", demo_mode=True)
    while not state.done:
        a, b = state.pair.a.combo, state.pair.b.combo
        axis = next(k for k in a if a[k] != b[k])
        pick = "a" if a[axis] == prefer.get(axis) else "b" if b[axis] == prefer.get(axis) else "a"
        state = service.submit_choice(state, state.pair.pair_id, pick)
    return state.history


def test_team_merges_everyone_and_flags_disagreement() -> None:
    domain = load_domain("domains/coding.yaml")
    agree = {"style_management": "theme", "type_detail": "explicit"}
    members = [
        team.Member("민수", _history("coding", {**agree, "code_structure": "separated"})),
        team.Member("지은", _history("coding", {**agree, "code_structure": "separated"})),
        team.Member("현우", _history("coding", {**agree, "code_structure": "compact"})),
    ]
    estimator, agreements = team.summarize(domain, members)
    by_axis = {a.axis: a for a in agreements}
    assert by_axis["style_management"].agreed and by_axis["style_management"].team_value == "theme"
    assert by_axis["type_detail"].agreed
    split = by_axis["code_structure"]
    assert not split.agreed
    assert split.votes == {"separated": 2, "compact": 1}
    assert split.team_value == "separated"  # 다수 쪽으로 합쳐진다
    assert not split.tied

    # 1:1 이면 동률로 표시한다 - 팀 프롬프트의 값은 다수결이 아니다.
    _, pair = team.summarize(domain, members[1:])
    assert {a.axis: a.tied for a in pair}["code_structure"] is True


def test_store_rules() -> None:
    store = team.TeamStore()
    history = _history("coding", {})
    with pytest.raises(team.TeamError, match="팀 코드"):
        store.add("x!", "coding", "a", history)
    with pytest.raises(team.TeamError, match="이름"):
        store.add("team-1", "coding", "", history)
    store.add("team-1", "coding", "민수", history)
    with pytest.raises(team.TeamError, match="다른 카테고리"):
        store.add("team-1", "summarization", "지은", history)
    # 같은 이름으로 다시 더하면 교체다 (다시 해 본 경우).
    store.add("team-1", "coding", "민수", history)
    assert [m.name for m in store.get("team-1")[1]] == ["민수"]


@pytest.fixture
def server(monkeypatch):
    monkeypatch.setattr(api_server, "LIVE", False)
    monkeypatch.setattr(api_server, "TEAMS", team.TeamStore())
    srv = ThreadingHTTPServer(("127.0.0.1", 0), api_server.ApiHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/api"
    srv.shutdown()


def _call(base, path, body=None):
    req = urllib.request.Request(base + path, None if body is None else json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read().decode("utf-8"))


def _finished_session(base, pick):
    _, data = _call(base, "/sessions", {"domainKey": "coding", "sourceText": SECRET_SOURCE})
    session = data["session"]
    while not session["done"]:
        _, data = _call(base, f"/sessions/{session['session_id']}/choices",
                        {"pairId": session["pair"]["pair_id"], "chosen": pick})
        session = data["session"]
    return session["session_id"]


def test_api_team_flow_without_leaking_sources(server) -> None:
    for name, pick in (("민수", "a"), ("지은", "b")):
        status, data = _call(server, "/teams/devteam/members",
                             {"sessionId": _finished_session(server, pick), "name": name})
        assert status == 200
    status, data = _call(server, "/teams/devteam")
    assert status == 200
    result = data["team"]
    assert result["members"] == ["민수", "지은"]
    assert {a["axis"] for a in result["agreements"]} == {"code_structure", "style_management", "type_detail"}
    assert all(a["label"] for a in result["agreements"])
    assert result["prompt"]
    assert any(e["key"] == "copilot" for e in result["exports"])
    # 팀 결과에는 누구의 원문도 들어가지 않는다.
    assert "Nightingale" not in json.dumps(data, ensure_ascii=False)


def test_api_team_errors(server) -> None:
    assert _call(server, "/teams/nobody-yet")[0] == 404
    session_id = _finished_session(server, "a")
    assert _call(server, "/teams/!!/members", {"sessionId": session_id, "name": "a"})[0] == 400
    # 끝나지 않은 세션은 더할 수 없다.
    _, data = _call(server, "/sessions", {"domainKey": "coding", "sourceText": SECRET_SOURCE})
    status, _ = _call(server, "/teams/devteam/members", {"sessionId": data["session"]["session_id"], "name": "a"})
    assert status == 400
