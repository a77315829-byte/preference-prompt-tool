"""'비슷함' 선택과 '이전 선택 수정'.

experiments/estimator_ablation.py 에서 앱 선택기는 같은 질문을 다시 묻지 않으므로
잘못 누른 한 번이 그대로 굳는다는 것이 드러났다 (잡음 10% 에서 정확 복원 66%, 다시
묻는 실험용 선택기는 83%). 사람이 직접 되돌릴 수 있어야 한다.
"""

import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

import api_server
import service
from engine.domain_loader import load_domain
from engine.estimator import Comparison, Estimator

SOURCE = "A short source text. It has two sentences."


def _start(domain_key="coding"):
    return service.start_session(SOURCE, domain_key, f"domains/{domain_key}.yaml", model="m", demo_mode=True)


def test_tie_moves_utilities_toward_each_other_and_starts_neutral() -> None:
    domain = load_domain("domains/coding.yaml")
    a = {"code_structure": "compact", "style_management": "direct", "type_detail": "inferred"}
    b = {**a, "code_structure": "separated"}
    est = Estimator(domain)
    est.update(Comparison(a, b, "tie"))
    assert est.utilities["code_structure"] == {"compact": 0.0, "separated": 0.0}
    est.update(Comparison(a, b, "a"))
    gap = est.utilities["code_structure"]["compact"] - est.utilities["code_structure"]["separated"]
    est.update(Comparison(a, b, "tie"))
    assert 0 < est.utilities["code_structure"]["compact"] - est.utilities["code_structure"]["separated"] < gap
    with pytest.raises(ValueError):
        est.update(Comparison(a, b, "c"))


def test_service_accepts_a_tie() -> None:
    state = _start()
    state = service.submit_choice(state, state.pair.pair_id, "tie")
    assert state.history[-1][2] == "tie"


def test_undo_returns_to_the_previous_question() -> None:
    state = _start("summarization")
    first_pair = (state.pair.a.combo, state.pair.b.combo)
    state = service.submit_choice(state, state.pair.pair_id, "a")
    state = service.undo_choice(state)
    assert state.history == [] and not state.done
    assert (state.pair.a.combo, state.pair.b.combo) == first_pair
    with pytest.raises(ValueError):
        service.undo_choice(state)


def test_undo_reopens_a_finished_session_with_its_round_limit() -> None:
    state = _start("coding")
    limit = state.total_rounds
    while not state.done:
        state = service.submit_choice(state, state.pair.pair_id, "a")
    state = service.undo_choice(state)
    assert not state.done and state.pair is not None
    assert state.total_rounds == limit and state.answered == limit - 1
    assert state.prompt is None and state.optimize_status == "idle"


def test_undo_and_tie_over_http(monkeypatch) -> None:
    monkeypatch.setattr(api_server, "LIVE", False)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), api_server.ApiHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}/api"

    def post(path, body):
        req = urllib.request.Request(base + path, json.dumps(body).encode(), {"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as err:
            return err.code, json.loads(err.read())

    try:
        _, body = post("/sessions", {"domainKey": "summarization", "sourceText": SOURCE})
        session = body["session"]
        assert post(f"/sessions/{session['session_id']}/undo", {})[0] == 400  # 아직 고른 것이 없다
        _, body = post(f"/sessions/{session['session_id']}/choices",
                       {"pairId": session["pair"]["pair_id"], "chosen": "tie"})
        assert body["session"]["answered"] == 1
        status, body = post(f"/sessions/{session['session_id']}/undo", {})
        assert status == 200 and body["session"]["answered"] == 0
    finally:
        srv.shutdown()
