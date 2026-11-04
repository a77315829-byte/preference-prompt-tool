import base64
import json
import sqlite3
import urllib.error
import urllib.request

import pytest

import handoffs
from app_db import Database, MIGRATIONS
from handoff_files import MAX_FILE_BYTES, preview_type, upload_fields
from handoffs import HandoffConflict, HandoffStore
from tests.test_handoffs import BODY, users
from tests.test_personal_prompts import request, signup
from tests.test_team import db, server


def upload(data=b"handoff contents\n", name="작업 메모.txt", revision=1):
    return {"revision": revision, "name": name, "data": base64.b64encode(data).decode()}


def get_file(base, path, cookie=None):
    req = urllib.request.Request(base + path, headers={"Cookie": cookie} if cookie else {})
    try:
        with urllib.request.urlopen(req) as response:
            return response.status, response.read(), response.headers
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), exc.headers


@pytest.mark.parametrize("bad", [
    {"name": "../secret.txt"}, {"name": "C:\\secret.txt"}, {"name": "a\r\nX-Test: yes"}, {"name": ".."},
    {"name": " "}, {"name": "a" * 181}, {"name": None}, {"data": ""}, {"data": "!bad!"},
    {"data": "데이터"}, {"data": 23},
])
def test_invalid_file_payloads_are_rejected(bad):
    with pytest.raises(ValueError):
        upload_fields({**upload(), **bad})


def test_file_size_boundary_and_safe_preview_types():
    data = b"x" * MAX_FILE_BYTES
    assert len(upload_fields(upload(data))[1]) == MAX_FILE_BYTES
    with pytest.raises(ValueError):
        upload_fields(upload(data + b"x"))
    assert preview_type(b"<svg onload='alert(1)'>") == "text/plain; charset=utf-8"
    assert upload_fields({**upload(b"<script>alert(1)</script>", "danger.html"), "content_type": "text/html"})[2].startswith("text/plain")
    assert preview_type(b"%PDF-1.7\n") == "application/pdf"
    assert preview_type(b"\x89PNG\r\n\x1a\n") == "image/png"
    assert preview_type(b"\xff\x00") == "application/octet-stream"


def test_files_follow_editor_permissions_versions_and_account_deletion(db):
    alice, bob, carol = users(db)
    store = HandoffStore(db)
    item = store.create(alice.id, {**BODY, "attachments": [{"id": "forged"}]})
    assert not item["body"].get("attachments")
    attached = store.change(alice.id, item["id"], "attach", upload())
    file = attached["body"]["attachments"][0]
    assert file["name"] == "작업 메모.txt" and file["size"] == len(b"handoff contents\n")
    shared = store.change(alice.id, item["id"], "share", {"revision": 2, "username": "bob"})
    with pytest.raises(PermissionError):
        store.change(bob.id, item["id"], "attach", upload(revision=3))
    assert store.file(bob.id, item["id"], file["id"], 3)["data"] == b"handoff contents\n"
    store.change(bob.id, item["id"], "claim", {"revision": 3})
    with pytest.raises(PermissionError):
        store.change(alice.id, item["id"], "detach", {"revision": 4, "fileId": file["id"]})
    # 일반 본문 갱신은 첨부 목록을 덮어쓰지 않는다.
    updated = store.change(bob.id, item["id"], "update", {**BODY, "revision": 4, "attachments": []})
    assert updated["body"]["attachments"] == [file]
    detached = store.change(bob.id, item["id"], "detach", {"revision": 5, "fileId": file["id"]})
    assert detached["body"]["attachments"] == []
    with pytest.raises(LookupError):
        store.file(bob.id, item["id"], file["id"], 6)
    assert HandoffStore(Database(db.path)).file(bob.id, item["id"], file["id"], 3)["data"] == b"handoff contents\n"
    assert store.history(bob.id, item["id"], 3)["body"] == shared["body"]
    with pytest.raises(LookupError):
        store.file(carol.id, item["id"], file["id"], 3)
    with db.connect() as conn:
        conn.execute("DELETE FROM users WHERE id=?", (bob.id,))
        assert conn.execute("SELECT COUNT(*) FROM handoff_files").fetchone()[0] == 1
        conn.execute("DELETE FROM users WHERE id=?", (alice.id,))
        assert conn.execute("SELECT COUNT(*) FROM handoff_files").fetchone()[0] == 0


def test_private_removed_files_other_work_and_revoked_recipients_are_inaccessible(db):
    alice, bob, carol = users(db)
    store = HandoffStore(db)
    item = store.create(alice.id, BODY)
    private = store.change(alice.id, item["id"], "attach", upload(b"PRIVATE"))
    private_id = private["body"]["attachments"][0]["id"]
    store.change(alice.id, item["id"], "detach", {"revision": 2, "fileId": private_id})
    store.change(alice.id, item["id"], "attach", upload(b"PUBLIC", revision=3))
    file_id = store.get(alice.id, item["id"])["body"]["attachments"][0]["id"]
    store.change(alice.id, item["id"], "share", {"revision": 4, "username": "bob"})
    for revision in (2, 3, 5):
        with pytest.raises(LookupError):
            store.file(bob.id, item["id"], private_id, revision)
    assert store.file(bob.id, item["id"], file_id, 5)["data"] == b"PUBLIC"
    other = store.create(alice.id, BODY)
    with pytest.raises(LookupError):
        store.file(alice.id, other["id"], file_id, 1)
    store.change(alice.id, item["id"], "share", {"revision": 5, "username": "carol"})
    with pytest.raises(LookupError):
        store.file(bob.id, item["id"], file_id, 5)
    with pytest.raises(LookupError):
        store.file(carol.id, item["id"], file_id, 5)
    assert store.file(carol.id, item["id"], file_id, 6)["data"] == b"PUBLIC"


def test_failed_attachment_transaction_leaves_no_orphans_and_retained_bytes_count(db, monkeypatch):
    alice, _, _ = users(db)
    store = HandoffStore(db)
    item = store.create(alice.id, BODY)
    store.change(alice.id, item["id"], "attach", upload(b"1234"))
    with pytest.raises(HandoffConflict):
        store.change(alice.id, item["id"], "attach", upload())
    monkeypatch.setattr(handoffs, "MAX_FILES", 1)
    with pytest.raises(ValueError, match="10개"):
        store.change(alice.id, item["id"], "attach", upload(revision=2))
    file_id = store.get(alice.id, item["id"])["body"]["attachments"][0]["id"]
    store.change(alice.id, item["id"], "detach", {"revision": 2, "fileId": file_id})
    monkeypatch.setattr(handoffs, "MAX_STORED_BYTES", 5)
    with pytest.raises(ValueError, match="20MB"):
        store.change(alice.id, item["id"], "attach", upload(b"12", revision=3))
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM handoff_files").fetchone()[0] == 1
    assert store.get(alice.id, item["id"])["revision"] == 3
    assert len(store.history(alice.id, item["id"])) == 3


def test_api_upload_download_preview_and_scoped_request_limit(server):
    alice, bob, carol = (signup(server, name) for name in ("alice", "bob", "carol"))
    item = request(server, "/handoffs", BODY, alice)[1]["handoff"]
    path = f"/handoffs/{item['id']}"
    data = "다음 담당자가 확인할 파일\n".encode() * 15000  # 기존 JSON 상한보다 큰 실제 파일
    assert request(server, path + "/attach", upload(), None)[0] == 401
    assert request(server, path + "/attach", upload(data), carol)[0] == 404
    status, result, _ = request(server, path + "/attach", upload(data), alice)
    assert status == 200
    file = result["handoff"]["body"]["attachments"][0]
    file_path = f"{path}/files/{file['id']}?revision=2"
    assert get_file(server, file_path)[0] == 401
    assert get_file(server, file_path, bob)[0] == 404
    assert request(server, path + "/share", {"username": "bob", "revision": 2}, alice)[0] == 200
    for cookie in (alice, bob):
        status, downloaded, headers = get_file(server, file_path.replace("=2", "=3"), cookie)
        assert status == 200 and downloaded == data
        assert headers["Content-Type"] == "application/octet-stream"
        assert headers["Content-Disposition"].startswith("attachment;") and "filename*=UTF-8''" in headers["Content-Disposition"]
        assert headers["Cache-Control"] == "no-store" and headers["X-Content-Type-Options"] == "nosniff"
    assert get_file(server, file_path, bob)[0] == 404
    status, opened, headers = get_file(server, file_path.replace("=2", "=3") + "&view=1", bob)
    assert status == 200 and opened == data and headers["Content-Type"].startswith("text/plain")
    assert headers["Content-Disposition"].startswith("inline;") and "sandbox" in headers["Content-Security-Policy"]
    assert get_file(server, file_path + "x", alice)[0] == 400
    assert request(server, path + "/update", {**BODY, "progress": "x" * 300000, "revision": 3}, alice)[0] == 400
    assert request(server, path + "/attach", upload(b"x" * (MAX_FILE_BYTES + 1), revision=3), alice)[0] == 400


def test_migrate_previous_handoff_history_without_files(tmp_path):
    path = tmp_path / "previous.db"
    with sqlite3.connect(path) as conn:
        for script in MIGRATIONS[:9]:
            conn.executescript(script)
        conn.execute("PRAGMA user_version = 9")
        conn.execute("INSERT INTO users VALUES (1,'alice','not-real','now')")
        conn.execute("INSERT INTO handoffs (id,owner_id,title,body_json,created_at,updated_at) VALUES ('old',1,'기존',?,'now','now')", (json.dumps(BODY),))
    store = HandoffStore(Database(path))
    attached = store.change(1, "old", "attach", upload())
    assert attached["body"]["purpose"] == BODY["purpose"]
    assert attached["revision"] == 2 and len(attached["body"]["attachments"]) == 1
