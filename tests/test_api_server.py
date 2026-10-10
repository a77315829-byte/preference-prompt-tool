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
    status, body = _post(server, "/sessions", {"domainKey": "summarization", "sourceText": SOURCE,
                                               "demoMode": False})
    assert status == 201
    session = json.loads(body)["session"]
    assert session["demo_mode"] is True
    assert session["demo_reason"] == "live_disabled"


def test_missing_openai_key_uses_demo_without_a_live_call(server, monkeypatch) -> None:
    monkeypatch.setattr(api_server, "LIVE", True)
    monkeypatch.setattr(api_server, "DEFAULT_MODEL", "openai/test-model")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    status, body = _post(server, "/sessions", {"domainKey": "coding", "sourceText": "예약 달력"})
    assert status == 201
    session = json.loads(body)["session"]
    assert session["demo_mode"] is True
    assert session["demo_reason"] == "api_key_missing"


def test_live_failure_falls_back_to_demo_without_leaking(
    server, monkeypatch, failing_live_generation, capsys
) -> None:
    monkeypatch.setattr(api_server, "LIVE", True)
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-key")
    monkeypatch.setattr(api_server, "LIVE_SESSIONS", DailyBudget(5))

    status, body = _post(server, "/sessions", {"domainKey": "summarization", "sourceText": SOURCE})
    assert status == 201
    session = json.loads(body)["session"]
    assert session["demo_mode"] is True
    assert session["demo_reason"] == "generation_failed"
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
    assert session["demo_reason"] == "generation_failed"
    assert "sk-abc" not in body


def test_daily_live_budget_falls_back_to_demo(server, monkeypatch) -> None:
    monkeypatch.setattr(api_server, "LIVE", True)
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-key")
    monkeypatch.setattr(api_server, "LIVE_SESSIONS", DailyBudget(0))
    status, body = _post(server, "/sessions", {"domainKey": "summarization", "sourceText": SOURCE})
    assert status == 201
    session = json.loads(body)["session"]
    assert session["demo_mode"] is True
    assert session["demo_reason"] == "daily_limit"


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


def test_session_ignores_client_chosen_model(server, monkeypatch) -> None:
    """세션 모델도 서버가 정한다. 요청 본문의 model 을 따르면 누구든 비싼
    모델 이름으로 서버 키를 쓸 수 있었다."""
    monkeypatch.setattr(api_server, "LIVE", False)
    status, body = _post(server, "/sessions", {
        "domainKey": "summarization", "sourceText": SOURCE, "model": "openai/some-expensive-model",
    })
    assert status == 201
    assert json.loads(body)["session"]["model"] == api_server.DEFAULT_MODEL


def test_finished_session_carries_exports(server, monkeypatch) -> None:
    """결과 화면이 도구별 내보내기를 그릴 수 있게, 끝난 세션에는 exports 가 붙는다.
    내보내기는 화면에 보이는 그 프롬프트여야 한다."""
    monkeypatch.setattr(api_server, "LIVE", False)
    status, body = _post(server, "/sessions", {"domainKey": "coding", "sourceText": SOURCE})
    session = json.loads(body)["session"]
    assert "exports" not in session  # 끝나기 전에는 없다
    while not session["done"]:
        _, body = _post(server, f"/sessions/{session['session_id']}/choices",
                        {"pairId": session["pair"]["pair_id"], "chosen": "a"})
        session = json.loads(body)["session"]
    exports = {e["key"]: e for e in session["exports"]}
    assert exports["copilot"]["path"] == ".github/copilot-instructions.md"
    assert session["prompt"] in exports["copilot"]["content"]
    assert exports["chatgpt"]["content"] == session["prompt"].strip()


def _get_raw(base: str, path: str, headers: dict | None = None):
    req = urllib.request.Request(base + path, headers=headers or {})
    with urllib.request.urlopen(req) as resp:
        return resp.status, dict(resp.headers), json.loads(resp.read().decode("utf-8"))


@pytest.mark.parametrize("live", [True, False])
def test_health_reports_live_mode(server, monkeypatch, live) -> None:
    """화면은 이 값으로 열리자마자 세션을 만들지 정한다. 실제 생성 모드에서
    자동으로 열면 방문만으로 하루 상한이 준다."""
    monkeypatch.setattr(api_server, "LIVE", live)
    monkeypatch.setattr(api_server, "DEFAULT_MODEL", "openai/test-model")
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-key")
    _, _, body = _get_raw(server, "/health")
    assert body["live"] is live
    assert body["liveConfigured"] is live


def test_health_discloses_missing_key_without_exposing_it(server, monkeypatch) -> None:
    monkeypatch.setattr(api_server, "LIVE", True)
    monkeypatch.setattr(api_server, "DEFAULT_MODEL", "openai/test-model")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    _, _, body = _get_raw(server, "/health")
    assert body["live"] is True
    assert body["liveConfigured"] is False
    assert "key" not in body


def test_no_cors_header_by_default(server, monkeypatch) -> None:
    """React 화면은 Vite 프록시로 같은 출처에서 부른다. "*" 를 주면 PPT_LIVE=1
    동안 아무 웹페이지나 서버 키로 다듬기·최적화를 부를 수 있다."""
    monkeypatch.setattr(api_server, "ALLOWED_ORIGINS", frozenset())
    _, headers, _ = _get_raw(server, "/health", {"Origin": "https://evil.example"})
    assert "Access-Control-Allow-Origin" not in headers


def test_cors_header_only_for_listed_origin(server, monkeypatch) -> None:
    monkeypatch.setattr(api_server, "ALLOWED_ORIGINS", frozenset({"https://app.example"}))
    _, ok, _ = _get_raw(server, "/health", {"Origin": "https://app.example"})
    assert ok["Access-Control-Allow-Origin"] == "https://app.example"
    _, other, _ = _get_raw(server, "/health", {"Origin": "https://evil.example"})
    assert "Access-Control-Allow-Origin" not in other


def test_negative_content_length_is_rejected(server) -> None:
    """음수면 rfile.read(-1) 이 연결이 끊길 때까지 기다리던 경로."""
    import http.client
    from urllib.parse import urlparse

    url = urlparse(server)
    conn = http.client.HTTPConnection(url.hostname, url.port, timeout=5)
    conn.putrequest("POST", url.path + "/sessions")
    conn.putheader("Content-Type", "application/json")
    conn.putheader("Content-Length", "-1")
    conn.endheaders()
    resp = conn.getresponse()
    assert resp.status == 400
    conn.close()
