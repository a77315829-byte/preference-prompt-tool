"""api_server.py 의 실제 생성 스위치(PPT_LIVE) 검증. 네트워크는 쓰지 않는다.

실제 호출이 실패해도 세션은 데모로 이어져야 하고, 공급자 에러 문구는
응답에 실리면 안 된다 - OpenAI 인증 에러는 키 일부를 문구에 담아 보낸다.
"""

import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

import api_server
import service
from budget import DailyBudget

LEAKY = "Incorrect API key provided: sk-abc*****wxyz"
SOURCE = "The council approved a housing plan. It adds homes. Critics worry about prices."


@pytest.fixture
def server():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), api_server.ApiHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/api"
    srv.shutdown()


def _post(base: str, path: str, body: dict) -> tuple[int, str]:
    req = urllib.request.Request(
        base + path, json.dumps(body).encode(), {"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as err:
        return err.code, err.read().decode("utf-8")


@pytest.fixture
def failing_live_generation(monkeypatch):
    """실제 생성 경로만 공급자 인증 에러를 내게 한다."""
    real = service._generate_pair

    def fake(state, *args, **kwargs):
        if not state.demo_mode:
            raise RuntimeError(LEAKY)
        return real(state, *args, **kwargs)

    monkeypatch.setattr(service, "_generate_pair", fake)


def test_live_off_keeps_demo(server, monkeypatch) -> None:
    monkeypatch.setattr(api_server, "LIVE", False)
    status, body = _post(server, "/sessions", {"domainKey": "summarization", "sourceText": SOURCE})
    assert status == 201
    assert json.loads(body)["session"]["demo_mode"] is True


def test_live_failure_falls_back_to_demo_without_leaking(
    server, monkeypatch, failing_live_generation, capsys
) -> None:
    monkeypatch.setattr(api_server, "LIVE", True)
    monkeypatch.setattr(api_server, "LIVE_SESSIONS", DailyBudget(5))

    status, body = _post(server, "/sessions", {"domainKey": "summarization", "sourceText": SOURCE})
    assert status == 201
    session = json.loads(body)["session"]
    assert session["demo_mode"] is True
    assert "sk-abc" not in body
    # 원인은 서버 터미널에는 남아야 한다.
    assert "sk-abc" in capsys.readouterr().out


def test_live_failure_mid_session_keeps_choices(
    server, monkeypatch, failing_live_generation
) -> None:
    """첫 쌍은 실제로 만들어졌는데 다음 쌍에서 실패해도 선택 이력은 이어진다."""
    monkeypatch.setattr(api_server, "LIVE", False)
    status, body = _post(server, "/sessions", {"domainKey": "summarization", "sourceText": SOURCE})
    session_id = json.loads(body)["session"]["session_id"]

    # 서버에 저장된 세션을 실제 생성 세션으로 바꿔 둔다.
    with api_server.SESSIONS_LOCK:
        live_state = api_server.SESSIONS[session_id]
        live_state.demo_mode = False
    pair_id = live_state.pair.pair_id

    status, body = _post(server, f"/sessions/{session_id}/choices", {"pairId": pair_id, "chosen": "a"})
    assert status == 200
    session = json.loads(body)["session"]
    assert session["answered"] == 1
    assert session["demo_mode"] is True
    assert "sk-abc" not in body


def test_daily_live_budget_falls_back_to_demo(server, monkeypatch) -> None:
    monkeypatch.setattr(api_server, "LIVE", True)
    monkeypatch.setattr(api_server, "LIVE_SESSIONS", DailyBudget(0))
    status, body = _post(server, "/sessions", {"domainKey": "summarization", "sourceText": SOURCE})
    assert status == 201
    assert json.loads(body)["session"]["demo_mode"] is True


def _get(base: str, path: str) -> tuple[int, dict]:
    try:
        with urllib.request.urlopen(base + path) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read().decode("utf-8"))


def _finished_session(base: str, live: bool) -> str:
    status, body = _post(base, "/sessions", {"domainKey": "summarization", "sourceText": SOURCE, "totalRounds": 2})
    session = json.loads(body)["session"]
    for _ in range(2):
        _, body = _post(
            base, f"/sessions/{session['session_id']}/choices",
            {"pairId": session["pair"]["pair_id"], "chosen": "a"},
        )
        session = json.loads(body)["session"]
    assert session["done"]
    if live:
        with api_server.SESSIONS_LOCK:
            api_server.SESSIONS[session["session_id"]].demo_mode = False
    return session["session_id"]


@pytest.fixture
def fresh_optimize_budget(monkeypatch):
    monkeypatch.setattr(api_server, "LIVE", False)
    monkeypatch.setattr(api_server, "DAILY_OPTIMIZATIONS", DailyBudget(5))
    monkeypatch.setattr(api_server, "OPTIMIZE_RUNS", {})


def test_optimize_replaces_seed_prompt(server, monkeypatch, fresh_optimize_budget) -> None:
    """React 화면의 프롬프트가 두세 줄에서 끝나던 이유가 이 단계의 부재였다."""
    import time

    def fake_optimize(state, on_progress=None, **_):
        on_progress(0.5)
        on_progress(1.0)
        return "OPTIMIZED PROMPT"

    monkeypatch.setattr(service, "optimize", fake_optimize)
    session_id = _finished_session(server, live=True)
    _, before = _get(server, f"/sessions/{session_id}")
    seed = before["session"]["prompt"]

    status, _ = _post(server, f"/sessions/{session_id}/optimize", {})
    assert status == 202
    for _ in range(50):
        _, polled = _get(server, f"/sessions/{session_id}")
        if polled["session"]["optimize_status"] != "running":
            break
        time.sleep(0.05)
    assert polled["session"]["optimize_status"] == "done"
    assert polled["session"]["optimize_progress"] == 1.0
    assert polled["session"]["prompt"] == "OPTIMIZED PROMPT" != seed


def test_optimize_refuses_demo_sessions(server, fresh_optimize_budget) -> None:
    session_id = _finished_session(server, live=False)
    status, body = _post(server, f"/sessions/{session_id}/optimize", {})
    assert status == 400
    assert "PPT_LIVE" in body


def test_optimize_per_session_cap(server, monkeypatch, fresh_optimize_budget) -> None:
    import time

    monkeypatch.setattr(service, "optimize", lambda state, on_progress=None, **_: "P")
    session_id = _finished_session(server, live=True)
    for _ in range(api_server.MAX_OPTIMIZATIONS_PER_SESSION):
        assert _post(server, f"/sessions/{session_id}/optimize", {})[0] == 202
        time.sleep(0.1)
    status, body = _post(server, f"/sessions/{session_id}/optimize", {})
    assert status == 400


def test_unchanged_optimization_is_reported_as_unchanged(server, monkeypatch, fresh_optimize_budget) -> None:
    """GEPA 가 시드를 그대로 고른 경우(실제 실행에서 나왔다)를 '적용됐다'로
    표시하지 않도록 바뀌었는지를 같이 준다."""
    import time

    monkeypatch.setattr(service, "optimize", lambda state, on_progress=None, **_: seed_holder["seed"])
    seed_holder = {}
    session_id = _finished_session(server, live=True)
    seed_holder["seed"] = _get(server, f"/sessions/{session_id}")[1]["session"]["prompt"]

    _post(server, f"/sessions/{session_id}/optimize", {})
    for _ in range(50):
        session = _get(server, f"/sessions/{session_id}")[1]["session"]
        if session["optimize_status"] != "running":
            break
        time.sleep(0.05)
    assert session["optimize_status"] == "done"
    assert session["optimize_changed"] is False
