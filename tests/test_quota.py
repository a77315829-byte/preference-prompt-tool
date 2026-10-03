"""사용자별 하루 상한 (quota.py) 과 API 연결.

고정하는 것: 사람마다 몫이 따로다, 익명 방문자는 한 몫을 나눠 쓴다, 서버 전체 상한도
지킨다, 재시작해도 남는다, 동시에 와도 상한을 넘지 않는다, 날이 바뀌면 다시 찬다."""

from __future__ import annotations

import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

import api_server
from app_db import Database
from auth import AuthService
from quota import ANON, Quota, subject_for


@pytest.fixture
def db(tmp_path) -> Database:
    return Database(tmp_path / "app.db")


def test_each_user_has_their_own_share(db) -> None:
    q = Quota(db, "polish", total=100, per_user=2)
    alice, bob = subject_for(1), subject_for(2)
    assert [q.consume(alice) for _ in range(3)] == [True, True, False]
    assert q.consume(bob) is True  # 앨리스가 다 써도 밥의 몫은 남는다
    assert q.left(alice) == 0 and q.left(bob) == 1


def test_anonymous_visitors_share_one_share(db) -> None:
    q = Quota(db, "polish", total=100, per_user=5, anon=2)
    assert [q.try_consume(ANON) for _ in range(3)] == [None, None, "subject"]
    assert q.consume(subject_for(1)) is True


def test_server_total_still_applies(db) -> None:
    q = Quota(db, "polish", total=3, per_user=2)
    assert q.consume(subject_for(1)) and q.consume(subject_for(1))
    assert q.consume(subject_for(2))
    assert q.try_consume(subject_for(2)) == "total"
    assert q.left(subject_for(3)) == 0


def test_usage_survives_a_restart(db) -> None:
    Quota(db, "polish", total=10, per_user=1).consume(subject_for(1))
    again = Quota(Database(db.path), "polish", total=10, per_user=1)
    assert again.consume(subject_for(1)) is False


def test_kinds_are_counted_separately(db) -> None:
    a = Quota(db, "polish", total=10, per_user=1)
    b = Quota(db, "workspace", total=10, per_user=1)
    assert a.consume(subject_for(1)) and b.consume(subject_for(1))


def test_a_new_day_refills(db) -> None:
    day = {"value": "2026-10-01"}
    q = Quota(db, "polish", total=10, per_user=1, clock=lambda: day["value"])
    assert q.consume(subject_for(1)) and not q.consume(subject_for(1))
    day["value"] = "2026-10-02"
    assert q.consume(subject_for(1))


def test_concurrent_requests_never_exceed_the_limit(db) -> None:
    """확인과 차감을 나누면 동시에 온 요청이 마지막 한 칸을 같이 가져간다."""
    q = Quota(db, "polish", total=1000, per_user=5)
    db.migrate()
    results: list[bool] = []
    lock = threading.Lock()

    def worker() -> None:
        ok = q.consume(subject_for(1))
        with lock:
            results.append(ok)

    threads = [threading.Thread(target=worker) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results.count(True) == 5


def test_negative_limits_are_rejected(db) -> None:
    with pytest.raises(ValueError):
        Quota(db, "polish", total=-1, per_user=1)


# --- API ----------------------------------------------------------------------


@pytest.fixture
def server(monkeypatch, tmp_path):
    db = Database(tmp_path / "app.db")
    monkeypatch.setattr(api_server, "DB", db)
    monkeypatch.setattr(api_server, "AUTH", AuthService(db))
    monkeypatch.setattr(api_server, "LIVE", True)
    monkeypatch.setattr(api_server, "DAILY_WORKSPACE_CALLS", Quota(db, "workspace", total=100, per_user=1, anon=1))
    srv = ThreadingHTTPServer(("127.0.0.1", 0), api_server.ApiHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/api"
    srv.shutdown()


def _post(base: str, path: str, body: dict, cookie: str = "") -> tuple[int, dict, dict]:
    headers = {"Content-Type": "application/json", **({"Cookie": cookie} if cookie else {})}
    req = urllib.request.Request(base + path, json.dumps(body).encode(), headers)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, dict(resp.headers), json.loads(resp.read())
    except urllib.error.HTTPError as err:
        return err.code, dict(err.headers), json.loads(err.read())


def _me(base: str, cookie: str = "") -> dict:
    req = urllib.request.Request(base + "/auth/me", headers={"Cookie": cookie} if cookie else {})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def test_api_shares_follow_login(server) -> None:
    # 빈 설명은 차감 전에 거절되므로 몫을 쓰지 않는다.
    assert _post(server, "/workspace/structure", {"description": ""})[0] == 400
    assert _me(server)["quota"]["workspace"] == 1
    # 익명 몫 1회를 다 쓰면 익명은 막히고, 로그인하라고 안내한다.
    assert api_server.DAILY_WORKSPACE_CALLS.consume(ANON) is True
    status, _, body = _post(server, "/workspace/structure", {"description": "비용 보고"})
    assert status == 400 and "로그인하면 개인 몫" in body["error"]

    # 로그인한 사람은 자기 몫이 따로 있다.
    _, headers, _ = _post(server, "/auth/signup", {"username": "alice", "password": "alice-password-1"})
    cookie = headers["Set-Cookie"].split(";")[0]
    assert _me(server, cookie)["quota"]["workspace"] == 1
    assert _me(server)["quota"]["workspace"] == 0
