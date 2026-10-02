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
