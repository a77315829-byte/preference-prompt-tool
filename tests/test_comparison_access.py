"""Real HTTP checks with isolated browser cookies; no model API calls."""
import hashlib
import http.cookiejar
import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

import api_server as api
import service
from app_db import Database
from auth import AuthService
from team import TeamStore


class Browser:
    def __init__(self, base):
        self.base = base
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def call(self, path, body=None, cookie=None):
        headers = {"Content-Type": "application/json"}
        if cookie is not None:
            headers["Cookie"] = cookie
        request = urllib.request.Request(self.base + path, None if body is None else json.dumps(body).encode(), headers)
        try:
            response = self.opener.open(request)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, json.loads(response.read())

    def cookies(self):
        return "; ".join(f"{cookie.name}={cookie.value}" for cookie in self.jar)

    def start(self, domain="coding", rounds=1):
        status, data = self.call("/sessions", {"domainKey": domain, "sourceText": "Private task. Keep these details private.", "totalRounds": rounds})
        assert status == 201, data
        return data["session"]

    def signup(self, name):
        status, data = self.call("/auth/signup", {"username": name, "password": "Example-password-142!"})
        assert status == 200, data
        return data["user"]


@pytest.fixture
def browsers(monkeypatch, tmp_path):
    db = Database(tmp_path / "access.db")
    monkeypatch.setattr(api, "DB", db)
    monkeypatch.setattr(api, "AUTH", AuthService(db))
    monkeypatch.setattr(api, "TEAMS", TeamStore(db))
    monkeypatch.setattr(api, "LIVE", False)
    monkeypatch.setattr(api, "ALLOW_SIGNUP", True)
    monkeypatch.setattr(api, "COOKIE_SECURE", False)
    for name in ("SESSIONS", "SESSION_STARTED", "SESSION_OWNERS", "COMPARISON_GUESTS", "OPTIMIZE_RUNS", "OPTIMIZE_REPORTS"):
        monkeypatch.setattr(api, name, {})
    import litellm
    monkeypatch.setattr(litellm, "completion", lambda *a, **k: pytest.fail("Paid API is forbidden"))
    server = ThreadingHTTPServer(("127.0.0.1", 0), api.ApiHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}/api"
    yield Browser(base), Browser(base)
    server.shutdown()
    server.server_close()


@pytest.mark.parametrize("accounts", [False, True])
@pytest.mark.parametrize("action", ["read", "choices", "undo", "optimize", "team"])
def test_foreign_browser_cannot_read_or_mutate(browsers, accounts, action):
    alice, bob = browsers
    if accounts:
        alice.signup("alice")
        bob.signup("bob")
    state = alice.start()
    sid = state["session_id"]
    path, body = f"/sessions/{sid}", None
    if action in ("choices", "undo", "optimize"):
        path += "/" + action
        body = {"pairId": state["pair"]["pair_id"], "chosen": "a"}
    elif action == "team":
        path, body = "/teams/never-created/members", {"sessionId": sid, "name": "intruder"}
    status, data = bob.call(path, body)
    assert status == 404 and data["code"] == "comparison_unavailable"
    assert "Private task" not in json.dumps(data)
    assert api.SESSIONS[sid].answered == 0 and not api.OPTIMIZE_RUNS
    assert alice.call(f"/sessions/{sid}")[0] == 200


def test_guest_cookie_required_and_promoted_on_login(browsers):
    alice, bob = browsers
    state = alice.start()
    sid = state["session_id"]
    old_cookie = alice.cookies()
    guest_cookie = next(iter(alice.jar))
    assert guest_cookie.has_nonstandard_attr("HttpOnly")
    assert guest_cookie.get_nonstandard_attr("SameSite") == "Lax"
    alice.signup("alice")
    assert alice.call(f"/sessions/{sid}")[0] == 200
    assert bob.call(f"/sessions/{sid}", cookie=old_cookie)[0] == 404
    status, data = alice.call(f"/sessions/{sid}/choices", {"pairId": state["pair"]["pair_id"], "chosen": "a"})
    assert status == 200 and data["session"]["done"]
    assert "SESSION_OWNERS" not in json.dumps(data) and "guest:" not in json.dumps(data)


@pytest.mark.parametrize("accounts", [False, True])
def test_logout_revokes_replayed_cookie_and_removes_all_metadata(browsers, accounts):
    alice, bob = browsers
    if accounts:
        alice.signup("alice")
    sid = alice.start()["session_id"]
    old_cookie = alice.cookies()
    api.OPTIMIZE_REPORTS[sid] = {"secret": "old report"}
    assert alice.call("/auth/logout", {})[0] == 200
    assert bob.call(f"/sessions/{sid}", cookie=old_cookie)[0] == 404
    for store in (api.SESSIONS, api.SESSION_STARTED, api.SESSION_OWNERS, api.OPTIMIZE_REPORTS):
        assert sid not in store


@pytest.mark.parametrize("action", ["read", "choices", "undo", "optimize", "team"])
def test_exact_ttl_boundary_is_checked_without_creating_another_session(browsers, monkeypatch, action):
    alice, _ = browsers
    alice.signup("alice")
    state = alice.start()
    sid = state["session_id"]
    clock = api.SESSION_STARTED[sid]
    monkeypatch.setattr(api.time, "monotonic", lambda: clock + api.SESSION_TTL_SECONDS)
    path, body = f"/sessions/{sid}", None
    if action in ("choices", "undo", "optimize"):
        path += "/" + action
        body = {"pairId": state["pair"]["pair_id"], "chosen": "a"}
    elif action == "team":
        path, body = "/teams/expired/members", {"sessionId": sid, "name": "alice"}
    assert alice.call(path, body)[0] == 404
    assert sid not in api.SESSIONS


def test_expired_login_cannot_fall_back_to_guest_or_spend_quota(browsers, monkeypatch):
    alice, _ = browsers
    alice.signup("alice")
    sid = alice.start()["session_id"]
    with api.DB.connect() as conn:
        conn.execute("UPDATE sessions SET expires_at = '2000-01-01T00:00:00+00:00'")
    monkeypatch.setattr(service, "start_session", lambda **k: pytest.fail("Expired login must be rejected before generation"))
    assert alice.call(f"/sessions/{sid}")[0] == 404
    assert alice.call("/sessions", {"sourceText": "private task"})[0] == 401


def test_unknown_owner_metadata_fails_closed(browsers):
    alice, _ = browsers
    sid = alice.start()["session_id"]
    api.SESSION_OWNERS.pop(sid)
    assert alice.call(f"/sessions/{sid}")[0] == 404


def test_account_switch_does_not_transfer_previous_account_data(browsers):
    alice, bob = browsers
    alice.signup("alice")
    sid = alice.start()["session_id"]
    bob.signup("bob")
    assert alice.call("/auth/login", {"username": "bob", "password": "Example-password-142!"})[0] == 200
    assert alice.call(f"/sessions/{sid}")[0] == 404 and sid not in api.SESSIONS


def test_late_choice_after_logout_does_not_resurrect_session(browsers, monkeypatch):
    alice, _ = browsers
    alice.signup("alice")
    state = alice.start(rounds=2)
    sid = state["session_id"]
    real = service.submit_choice
    def logout_during_generation(*args, **kwargs):
        updated = real(*args, **kwargs)
        assert alice.call("/auth/logout", {})[0] == 200
        return updated
    monkeypatch.setattr(service, "submit_choice", logout_during_generation)
    status, _ = alice.call(f"/sessions/{sid}/choices", {"pairId": state["pair"]["pair_id"], "chosen": "a"})
    assert status == 404 and sid not in api.SESSIONS


def test_optimization_finishing_after_logout_cannot_restore_report(browsers, monkeypatch):
    alice, _ = browsers
    alice.signup("alice")
    state = alice.start()
    sid = state["session_id"]
    assert alice.call(f"/sessions/{sid}/choices", {"pairId": state["pair"]["pair_id"], "chosen": "a"})[0] == 200
    api.SESSIONS[sid].demo_mode = False
    monkeypatch.setattr(service, "check_optimizable", lambda *_: None)
    monkeypatch.setattr(api, "_take", lambda *_: None)
    started, finish = threading.Event(), threading.Event()
    def optimize(*args, **kwargs):
        started.set()
        assert finish.wait(5)
        kwargs["report"]["secret"] = "not retained"
        return "late prompt"
    monkeypatch.setattr(service, "optimize", optimize)
    assert alice.call(f"/sessions/{sid}/optimize", {})[0] == 202
    assert started.wait(5)
    assert alice.call("/auth/logout", {})[0] == 200
    finish.set()
    # Synchronize with worker exit instead of assuming a sleep duration.
    for worker in threading.enumerate():
        if worker.name.endswith("(work)"):
            worker.join(5)
    assert sid not in api.SESSIONS and sid not in api.OPTIMIZE_REPORTS
