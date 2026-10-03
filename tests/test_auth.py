"""로그인 (auth.py, app_db.py) 과 그 HTTP 경로.

고정하는 것: 비밀번호·토큰 원문이 DB 에 없다, 틀린 이유를 구분해 알려 주지 않는다,
실패가 쌓이면 막는다, 다른 사이트에서 보낸 POST 는 받지 않는다, 쿠키 속성."""

from __future__ import annotations

import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

import api_server
import app_db
import auth
from app_db import Database
from auth import AuthError, AuthService, FailureLimiter, TooManyAttempts


@pytest.fixture
def db(tmp_path) -> Database:
    return Database(tmp_path / "app.db")


@pytest.fixture
def service(db) -> AuthService:
    return AuthService(db)


# --- 비밀번호 -------------------------------------------------------------------


def test_password_hash_roundtrip_and_salt() -> None:
    a, b = auth.hash_password("pw-12345678"), auth.hash_password("pw-12345678")
    assert a != b  # 소금이 달라 같은 비밀번호도 해시가 다르다
    assert auth.verify_password("pw-12345678", a)
    assert not auth.verify_password("pw-12345679", a)
    assert not auth.verify_password("pw-12345678", "garbage")


def test_db_never_holds_the_password_or_the_token(service, db) -> None:
    _, token = service.signup("alice", "correct-horse-1")
    with db.connect() as conn:
        dump = "\n".join(conn.iterdump())
    assert "correct-horse-1" not in dump
    assert token not in dump


# --- 가입 · 로그인 ---------------------------------------------------------------


@pytest.mark.parametrize("username, password, message", [
    ("ab", "long-enough-1", "아이디"),
    ("bad name", "long-enough-1", "아이디"),
    ("alice", "short", "비밀번호"),
    ("alice1234", "Alice1234", "다르게"),
])
def test_signup_rejects_weak_input(service, username, password, message) -> None:
    with pytest.raises(AuthError, match=message):
        service.signup(username, password)


def test_usernames_are_unique_ignoring_case(service) -> None:
    service.signup("alice", "correct-horse-1")
    with pytest.raises(AuthError, match="이미"):
        service.signup("ALICE", "correct-horse-2")


def test_login_and_session(service) -> None:
    user, _ = service.signup("alice", "correct-horse-1")
    logged_in, token = service.login("Alice", "correct-horse-1")
    assert logged_in == user
    assert service.user_for(token) == user
    service.logout(token)
    assert service.user_for(token) is None


def test_wrong_password_and_unknown_user_look_the_same(service) -> None:
    service.signup("alice", "correct-horse-1")
    with pytest.raises(AuthError) as wrong:
        service.login("alice", "nope-nope-nope")
    with pytest.raises(AuthError) as unknown:
        service.login("nobody", "nope-nope-nope")
    assert str(wrong.value) == str(unknown.value)


def test_repeated_failures_lock_the_username_then_unlock(db) -> None:
    now = [1000.0]
    service = AuthService(db, FailureLimiter(clock=lambda: now[0]))
    service.signup("alice", "correct-horse-1")
    for _ in range(auth.MAX_FAILS_PER_USERNAME):
        with pytest.raises(AuthError):
            service.login("alice", "wrong-password")
    with pytest.raises(TooManyAttempts):
        service.login("alice", "correct-horse-1")  # 맞는 비밀번호도 잠시 막힌다
    now[0] += auth.FAIL_WINDOW_SECONDS + 1
    assert service.login("alice", "correct-horse-1")[0].username == "alice"


def test_expired_session_is_not_accepted(service, db) -> None:
    user, token = service.signup("alice", "correct-horse-1")
    with db.connect() as conn:
        conn.execute("UPDATE sessions SET expires_at = '2000-01-01T00:00:00+00:00'")
    assert service.user_for(token) is None


def test_migrations_are_idempotent(tmp_path) -> None:
    db = Database(tmp_path / "app.db")
    db.migrate()
    db.migrate()
    with db.connect() as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == len(app_db.MIGRATIONS)


# --- HTTP ---------------------------------------------------------------------


@pytest.fixture
def server(monkeypatch, tmp_path):
    db = Database(tmp_path / "app.db")
    monkeypatch.setattr(api_server, "DB", db)
    monkeypatch.setattr(api_server, "AUTH", AuthService(db))
    srv = ThreadingHTTPServer(("127.0.0.1", 0), api_server.ApiHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def _post(base: str, path: str, body: dict, headers: dict | None = None):
    req = urllib.request.Request(base + path, json.dumps(body).encode(),
                                 {"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, dict(resp.headers), json.loads(resp.read())
    except urllib.error.HTTPError as err:
        return err.code, dict(err.headers), json.loads(err.read())


def test_signup_sets_a_safe_cookie_and_me_reads_it(server) -> None:
    status, headers, body = _post(server, "/api/auth/signup", {"username": "alice", "password": "correct-horse-1"})
    assert status == 200 and body["user"]["username"] == "alice"
    cookie = headers["Set-Cookie"]
    assert "HttpOnly" in cookie and "SameSite=Lax" in cookie and "Path=/" in cookie
    assert "password" not in json.dumps(body)

    req = urllib.request.Request(server + "/api/auth/me", headers={"Cookie": cookie.split(";")[0]})
    with urllib.request.urlopen(req) as resp:
        assert json.loads(resp.read())["user"]["username"] == "alice"
    with urllib.request.urlopen(server + "/api/auth/me") as resp:
        assert json.loads(resp.read())["user"] is None


def test_login_lockout_is_a_429(server) -> None:
    _post(server, "/api/auth/signup", {"username": "alice", "password": "correct-horse-1"})
    codes = [_post(server, "/api/auth/login", {"username": "alice", "password": "wrong-pass"})[0]
             for _ in range(auth.MAX_FAILS_PER_USERNAME + 1)]
    assert codes[:-1] == [400] * auth.MAX_FAILS_PER_USERNAME and codes[-1] == 429


def test_signup_can_be_closed(server, monkeypatch) -> None:
    monkeypatch.setattr(api_server, "ALLOW_SIGNUP", False)
    status, _, body = _post(server, "/api/auth/signup", {"username": "alice", "password": "correct-horse-1"})
    assert status == 403


def test_cross_site_posts_are_refused(server) -> None:
    """다른 사이트가 로그인 쿠키를 이용해 요청하지 못하게 (CSRF)."""
    status, _, _ = _post(server, "/api/auth/login", {"username": "a", "password": "b"},
                         headers={"Origin": "https://evil.example"})
    assert status == 403
    host = server.removeprefix("http://")
    status, _, _ = _post(server, "/api/auth/signup", {"username": "alice", "password": "correct-horse-1"},
                         headers={"Origin": f"http://{host}"})
    assert status == 200


def test_same_site_requests_through_a_dev_proxy_pass(server) -> None:
    """실제 브라우저 확인에서 나온 결함: Vite 프록시가 Host 를 127.0.0.1:8000 으로
    바꿔서, 같은 화면의 로그인 요청이 '다른 사이트'로 막혔다. 프록시가 알려 주는 원래
    Host(X-Forwarded-Host)와 Origin 이 같으면 같은 사이트다."""
    status, _, _ = _post(server, "/api/auth/signup", {"username": "alice", "password": "correct-horse-1"},
                         headers={"Origin": "http://localhost:5175", "X-Forwarded-Host": "localhost:5175"})
    assert status == 200
    status, _, _ = _post(server, "/api/auth/login", {"username": "alice", "password": "correct-horse-1"},
                         headers={"Origin": "https://evil.example", "X-Forwarded-Host": "localhost:5175"})
    assert status == 403


def test_address_lockout_through_the_dev_proxy_is_per_visitor(server) -> None:
    """Vite 프록시를 거치면 서버가 보는 주소는 모두 127.0.0.1 이다. 그 주소로 실패를 세면
    누구 한 명이 20번 틀릴 때 모든 사람의 로그인이 15분 막혔다. 프록시가 덧붙이는
    X-Forwarded-For 의 마지막 주소(프록시가 직접 본 주소)로 센다 - 앞부분은 방문자가
    마음대로 적을 수 있으므로 쓰지 않는다."""
    _post(server, "/api/auth/signup", {"username": "bob", "password": "correct-horse-1"})
    attacker = {"X-Forwarded-For": "10.0.0.7, 10.0.0.66"}  # 앞은 위조, 뒤가 실제
    for i in range(auth.MAX_FAILS_PER_ADDRESS):
        _post(server, "/api/auth/login", {"username": f"guess{i}", "password": "wrong-pass"}, headers=attacker)
    assert _post(server, "/api/auth/login", {"username": "bob", "password": "correct-horse-1"},
                 headers=attacker)[0] == 429
    # 다른 방문자 - 공격자가 위조해 적은 10.0.0.7 이라도 - 는 막히지 않는다.
    status, _, body = _post(server, "/api/auth/login", {"username": "bob", "password": "correct-horse-1"},
                            headers={"X-Forwarded-For": "10.0.0.7"})
    assert status == 200 and body["user"]["username"] == "bob"


# --- 계정 관리: 비밀번호 변경 · 탈퇴 ------------------------------------------------


def test_change_password_revokes_every_session_and_issues_a_new_one(service) -> None:
    user, phone = service.signup("alice", "correct-horse-1")
    _, laptop = service.login("alice", "correct-horse-1")
    new_token = service.change_password(user, "correct-horse-1", "battery-staple-2")
    assert service.user_for(phone) is None and service.user_for(laptop) is None
    assert service.user_for(new_token) == user
    with pytest.raises(AuthError):
        service.login("alice", "correct-horse-1")
    assert service.login("alice", "battery-staple-2")[0] == user


@pytest.mark.parametrize("current, new, message", [
    ("wrong-password", "battery-staple-2", "지금 비밀번호"),
    ("correct-horse-1", "short", "새 비밀번호"),
    ("correct-horse-1", "correct-horse-1", "같습니다"),
    ("correct-horse-1", "ALICE", "새 비밀번호"),
])
def test_change_password_rejects_bad_requests(service, current, new, message) -> None:
    user, token = service.signup("alice", "correct-horse-1")
    with pytest.raises(AuthError, match=message):
        service.change_password(user, current, new)
    assert service.user_for(token) == user  # 실패하면 세션도 그대로


def test_password_recheck_counts_toward_lockout(db) -> None:
    now = [1000.0]
    service = AuthService(db, FailureLimiter(clock=lambda: now[0]))
    user, _ = service.signup("alice", "correct-horse-1")
    for _ in range(auth.MAX_FAILS_PER_USERNAME):
        with pytest.raises(AuthError):
            service.change_password(user, "guess-guess-1", "battery-staple-2")
    with pytest.raises(TooManyAttempts):
        service.delete_account(user, "correct-horse-1")


def test_delete_account_removes_user_data_and_reports_shared_projects(service, db) -> None:
    from prompt_workspace.examples import synthetic_cost
    from prompt_workspace.models import new_project
    from prompt_workspace.store import ProjectStore

    alice, alice_token = service.signup("alice", "correct-horse-1")
    bob, _ = service.signup("bob", "bob-password-1")
    store = ProjectStore(db)
    project = new_project("공유한 것", synthetic_cost.SAMPLE_DESCRIPTION)
    project["requirements"] = synthetic_cost.sample_requirements()
    store.save(alice.id, project)
    store.share(alice.id, project["id"], "bob", "viewer")
    assert service.owned_shared_count(alice) == 1

    with pytest.raises(AuthError):
        service.delete_account(alice, "wrong-password")
    service.delete_account(alice, "correct-horse-1")

    assert service.user_for(alice_token) is None
    assert store.list(bob.id) == []  # 소유자가 탈퇴하면 공유받은 사람에게서도 사라진다
    with db.connect() as conn:
        for table in ("users", "sessions", "workspace_projects", "workspace_versions", "workspace_members"):
            rows = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            assert rows == (1 if table in ("users", "sessions") else 0), table
    # 같은 아이디로 다시 가입할 수 있다.
    service.signup("alice", "new-life-12345")


def test_account_routes_over_http(server) -> None:
    status, headers, _ = _post(server, "/api/auth/signup", {"username": "alice", "password": "correct-horse-1"})
    cookie = headers["Set-Cookie"].split(";")[0]

    assert _post(server, "/api/auth/password", {"current": "x", "new": "y"})[0] == 401  # 로그인 없이
    status, _, body = _post(server, "/api/auth/password", {"current": "wrong-pass", "new": "battery-staple-2"},
                            headers={"Cookie": cookie})
    assert status == 400 and "지금 비밀번호" in body["error"]
    status, headers, _ = _post(server, "/api/auth/password",
                               {"current": "correct-horse-1", "new": "battery-staple-2"}, headers={"Cookie": cookie})
    assert status == 200
    new_cookie = headers["Set-Cookie"].split(";")[0]
    assert new_cookie != cookie
    # 옛 쿠키는 더는 통하지 않는다.
    assert _post(server, "/api/auth/delete", {"password": "battery-staple-2"}, headers={"Cookie": cookie})[0] == 401

    status, headers, body = _post(server, "/api/auth/delete", {"password": "battery-staple-2"},
                                  headers={"Cookie": new_cookie})
    assert status == 200 and body["user"] is None and "Max-Age=0" in headers["Set-Cookie"]
    status, _, _ = _post(server, "/api/auth/login", {"username": "alice", "password": "battery-staple-2"})
    assert status == 400


def test_signups_from_one_address_are_limited(db, monkeypatch) -> None:
    """계정을 계속 만들면 팀·저장 공간의 사람별 상한을 우회할 수 있다."""
    monkeypatch.setattr(auth, "MAX_SIGNUPS_PER_ADDRESS", 2)
    service = AuthService(db)
    service.signup("user1", "password-123", address="10.0.0.1")
    service.signup("user2", "password-123", address="10.0.0.1")
    with pytest.raises(TooManyAttempts):
        service.signup("user3", "password-123", address="10.0.0.1")
    service.signup("user4", "password-123", address="10.0.0.2")
