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
