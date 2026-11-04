"""Public entry point checks: asset isolation, same-origin API and cookie setup."""
import http.client
import json
import threading
from pathlib import Path

import pytest

import api_server
from app_db import Database
from auth import AuthService
from hosting_server import HostedServer, make_handler


@pytest.fixture
def hosted(tmp_path, monkeypatch):
    build = tmp_path / "dist"
    build.mkdir()
    (build / "index.html").write_text("<html>hosted app</html>", encoding="utf-8")
    (build / "assets").mkdir()
    (build / "assets/app.js").write_text("console.log('app')", encoding="utf-8")
    (build / "assets/app.js.map").write_text("source-map-private", encoding="utf-8")
    (build / "assets/UPPER.MAP").write_text("source-map-private", encoding="utf-8")
    (tmp_path / "private.db").write_text("outside-build", encoding="utf-8")
    (build / ".env").write_text("fixture-secret", encoding="utf-8")
    database = Database(tmp_path / "test.db")
    monkeypatch.setattr(api_server, "DB", database)
    monkeypatch.setattr(api_server, "AUTH", AuthService(database))
    monkeypatch.setattr(api_server, "LIVE", False)
    monkeypatch.setattr(api_server, "COOKIE_SECURE", True)
    monkeypatch.setattr(api_server, "ALLOW_SIGNUP", True)
    monkeypatch.setattr(api_server, "ALLOWED_ORIGINS", frozenset())
    with HostedServer(("127.0.0.1", 0), make_handler(build)) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        yield server.server_address
        server.shutdown()
        thread.join(timeout=3)


def request(address, path, method="GET", body=None, headers=None):
    conn = http.client.HTTPConnection(*address, timeout=5)
    if body is not None:
        body = json.dumps(body)
        headers = {"Content-Type": "application/json", **(headers or {})}
    try:
        conn.request(method, path, body, headers or {})
        response = conn.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        conn.close()


def test_root_with_handoff_query_and_api_share_the_server(hosted):
    status, headers, body = request(hosted, "/?handoff=example")
    assert status == 200 and b"hosted app" in body
    assert headers["Content-Type"] == "text/html"
    assert headers["X-Content-Type-Options"] == "nosniff"
    status, _, body = request(hosted, "/api/health")
    assert status == 200 and json.loads(body)["ok"]


def test_javascript_mime_and_head_length(hosted):
    status, headers, body = request(hosted, "/assets/app.js")
    assert status == 200 and headers["Content-Type"] == "text/javascript"
    head_status, head_headers, head_body = request(hosted, "/assets/app.js", "HEAD")
    assert head_status == 200 and head_body == b""
    assert head_headers["Content-Length"] == str(len(body))


@pytest.mark.parametrize("path", [
    "/../private.db", "/%2e%2e/private.db", "/assets/%2e%2e/%2e%2e/private.db",
    "/.env", "/%2eenv", "/assets%5c..%5c.env", "/%00", "/private.db",
    "/assets/missing.js", "/assets/app.js.map", "/assets/UPPER.MAP", "/api/missing",
])
def test_private_paths_and_missing_assets_are_not_spa_fallbacks(hosted, path):
    status, _, body = request(hosted, path)
    assert status == 404
    assert b"fixture-secret" not in body and b"outside-build" not in body
    assert b"hosted app" not in body


def test_same_origin_login_cookie_is_secure(hosted):
    origin = f"http://{hosted[0]}:{hosted[1]}"
    status, headers, body = request(hosted, "/api/auth/signup", "POST",
        {"username": "hosted_demo", "password": "Fixture-test-2026!"}, {"Origin": origin})
    assert status == 200, body
    cookie = headers["Set-Cookie"]
    assert all(flag in cookie for flag in ("HttpOnly", "SameSite=Lax", "Secure"))


def test_forwarded_host_cannot_bypass_cross_site_protection(hosted):
    status, _, _ = request(hosted, "/api/auth/signup", "POST",
        {"username": "forged_demo", "password": "Fixture-test-2026!"},
        {"Origin": "https://attacker.example", "X-Forwarded-Host": "attacker.example"})
    assert status == 403


def test_missing_frontend_build_fails_before_listening(tmp_path):
    with pytest.raises(ValueError, match="Build the frontend"):
        make_handler(tmp_path)


def test_symlink_outside_build_is_not_served(tmp_path):
    build = tmp_path / "dist"
    build.mkdir()
    (build / "index.html").write_text("app")
    secret = tmp_path / "outside.txt"
    secret.write_text("outside-build")
    try:
        (build / "public.txt").symlink_to(secret)
    except OSError:
        pytest.skip("Host does not permit creating symlinks")
    with HostedServer(("127.0.0.1", 0), make_handler(build)) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            assert request(server.server_address, "/public.txt")[0] == 404
        finally:
            server.shutdown()
            thread.join(timeout=3)
