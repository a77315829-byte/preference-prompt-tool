import copy
from concurrent.futures import ThreadPoolExecutor
import json
import sqlite3

import pytest

import api_server
from app_db import Database, MIGRATIONS
from auth import AuthService
import handoffs
from handoffs import HandoffConflict, HandoffStore, handoff_fields
from personal_prompts import PersonalPromptStore
from tests.test_personal_prompts import request, signup
from tests.test_team import db, server

BODY = {"title": "로그인 API 이어받기", "purpose": "팀원 로그인 기능 완성", "progress": "엔드포인트 작성, 오류 처리 미완료",
    "remaining": "예외 응답과 테스트 추가", "references": ["src/auth.py", "https://example.test/spec"], "prompt": "Python으로 역할별 함수를 나눠 작성하라."}


def users(db):
    auth = AuthService(db)
    return [auth.signup(name, f"{name}-password-123")[0] for name in ("alice", "bob", "carol")]


def test_handoff_lifecycle_keeps_shared_snapshot_and_original_preference(db):
    alice, bob, carol = users(db)
    store = HandoffStore(db)
    original = PersonalPromptStore(db).create(alice.id, {"title": "내 방식", "domainKey": "coding", "prompt": BODY["prompt"]})
    item = store.create(alice.id, {**BODY, "owner_id": carol.id, "recipient_id": bob.id, "sourceText": "NOT SAVED"})
    assert item["owner"] == "alice" and item["recipient"] is None and item["status"] == "draft"
    assert store.list_for(bob.id) == []
    assert "body" not in store.list_for(alice.id)[0] and "NOT SAVED" not in json.dumps(item)
    assert PersonalPromptStore(db).get(alice.id, original["id"]) == original
    with pytest.raises(LookupError):
        store.get(bob.id, item["id"])
    shared = store.change(alice.id, item["id"], "share", {"revision": 1, "username": "BOB"})
    before = copy.deepcopy(shared)
    assert shared["status"] == "shared" and store.get(bob.id, item["id"])["can_claim"]
    assert [v["revision"] for v in store.history(bob.id, item["id"])] == [2]
    with pytest.raises(LookupError):
        store.history(bob.id, item["id"], 1)
    with pytest.raises(PermissionError):
        store.change(bob.id, item["id"], "update", {**BODY, "revision": 2})
    active = store.change(bob.id, item["id"], "claim", {"revision": 2})
    assert active["status"] == "active" and active["can_edit"]
    with pytest.raises(PermissionError):
        store.change(alice.id, item["id"], "update", {**BODY, "revision": 3})
    with pytest.raises(PermissionError):
        store.change(alice.id, item["id"], "share", {"username": "carol", "revision": 3})
    updated = store.change(bob.id, item["id"], "update", {**BODY, "progress": "테스트 외 구현 완료", "remaining": "남은 테스트", "revision": 3})
    assert updated["revision"] == 4
    assert store.history(bob.id, item["id"], 2)["body"] == before["body"]
    assert PersonalPromptStore(db).get(alice.id, original["id"]) == original
    done = store.change(bob.id, item["id"], "complete", {"revision": 4})
    assert done["status"] == "done" and done["can_reopen"] and not done["can_edit"]
    with pytest.raises(PermissionError):
        store.change(bob.id, item["id"], "update", {**BODY, "revision": 5})
    assert store.change(bob.id, item["id"], "reopen", {"revision": 5})["can_edit"]
    assert HandoffStore(Database(db.path)).get(alice.id, item["id"])["body"]["remaining"] == "남은 테스트"
    assert store.list_for(carol.id) == []


@pytest.mark.parametrize("changes", [
    {"title": " "}, {"title": "a" * 101}, {"purpose": ""}, {"progress": None}, {"remaining": ""},
    {"purpose": "a" * 3001}, {"progress": "a" * 6001}, {"remaining": "a" * 6001}, {"prompt": "a" * 20001},
    {"references": "src/a.py"}, {"references": ["a"] * 21}, {"references": [42]}, {"references": ["a\nb"]},
    {"references": ["javascript:alert(1)"]}, {"references": ["data:text/html,a"]}, {"references": ["file:///C:/a.txt"]},
    {"references": ["https://"]}, {"references": ["http://[broken"]},
])
def test_invalid_handoff_fields_are_rejected(changes):
    with pytest.raises(ValueError):
        handoff_fields({**BODY, **changes})


def test_references_are_paths_or_safe_links_and_prompt_is_optional():
    _, body = handoff_fields({**BODY, "prompt": "", "references": ["src/a.py", "C:\\project\\a.py", "https://example.test/a", "src/a.py"]})
    assert body["prompt"] == "" and len(body["references"]) == 3


def test_private_drafts_and_revoked_recipient_history_remain_private(db):
    alice, bob, carol = users(db)
    store = HandoffStore(db)
    item = store.create(alice.id, {**BODY, "progress": "PRIVATE EARLY DRAFT"})
    store.change(alice.id, item["id"], "update", {**BODY, "revision": 1})
    store.change(alice.id, item["id"], "share", {"username": "bob", "revision": 2})
    assert len(store.history(alice.id, item["id"])) == 3
    assert [v["revision"] for v in store.history(bob.id, item["id"])] == [3]
    with pytest.raises(LookupError):
        store.history(bob.id, item["id"], 1)
    assert "PRIVATE" not in json.dumps(store.history(bob.id, item["id"], 3))
    store.change(alice.id, item["id"], "share", {"username": "carol", "revision": 3})
    for operation in (lambda: store.get(bob.id, item["id"]), lambda: store.history(bob.id, item["id"]), lambda: store.history(bob.id, item["id"], 3)):
        with pytest.raises(LookupError):
            operation()
    assert store.list_for(bob.id) == []
    assert [v["revision"] for v in store.history(carol.id, item["id"])] == [4]


def test_share_failures_stale_versions_and_concurrent_claims_do_not_overwrite(db, monkeypatch):
    alice, bob, _ = users(db)
    store = HandoffStore(db)
    item = store.create(alice.id, BODY)
    for username in ("alice", "missing", "bad user"):
        with pytest.raises(ValueError):
            store.change(alice.id, item["id"], "share", {"username": username, "revision": 1})
    assert store.get(alice.id, item["id"]) == item
    shared = store.change(alice.id, item["id"], "share", {"username": "bob", "revision": 1})
    def claim():
        try:
            store.change(bob.id, item["id"], "claim", {"revision": shared["revision"]})
            return "ok"
        except HandoffConflict:
            return "conflict"
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: claim(), range(2))) == ["conflict", "ok"]
    with pytest.raises(HandoffConflict):
        store.change(bob.id, item["id"], "update", {**BODY, "revision": 2})
    assert len(store.history(bob.id, item["id"])) == 2
    monkeypatch.setattr(handoffs, "MAX_HANDOFFS", 1)
    with pytest.raises(ValueError):
        store.create(alice.id, BODY)


def test_api_auth_access_actions_and_no_model_or_quota_calls(server, monkeypatch):
    monkeypatch.setattr(api_server, "_take", lambda *_: pytest.fail("인수인계는 모델 사용량을 차감하지 않는다"))
    monkeypatch.setattr(api_server.service.generator, "generate_with_prompt", lambda *_a, **_k: pytest.fail("모델 호출 없음"))
    assert request(server, "/handoffs")[0] == 401
    assert request(server, "/handoffs", BODY)[0] == 401
    alice, bob, carol = (signup(server, name) for name in ("alice", "bob", "carol"))
    status, data, _ = request(server, "/handoffs", BODY, alice)
    assert status == 201
    item = data["handoff"]
    path = f"/handoffs/{item['id']}"
    for suffix in ("", "/history", "/history/1"):
        assert request(server, path + suffix, cookie=carol)[0] == 404
    assert request(server, path + "/share", {"username": "bob", "revision": 1}, alice)[0] == 200
    assert request(server, path + "/history/1", cookie=bob)[0] == 404
    assert request(server, path, cookie=bob)[1]["handoff"]["status"] == "shared"
    assert request(server, path + "/update", {**BODY, "revision": 2}, bob)[0] == 403
    assert request(server, path + "/claim", {"revision": 2}, bob)[0] == 200
    assert request(server, path + "/claim", {"revision": 2}, bob)[0] == 409
    assert request(server, path + "/update", {**BODY, "revision": 3}, alice)[0] == 403
    assert request(server, path + "/update", {**BODY, "progress": "테스트 추가", "revision": 3}, bob)[0] == 200
    assert request(server, path + "/complete", {"revision": 4}, bob)[0] == 200
    assert request(server, path + "/reopen", {"revision": 5}, bob)[0] == 200
    assert request(server, path + "/update", {**BODY, "revision": True}, bob)[0] == 400
    assert request(server, "/handoffs", cookie=alice)[1]["handoffs"][0]["role"] == "owner"
    assert request(server, "/handoffs", cookie=bob)[1]["handoffs"][0]["role"] == "recipient"
    assert request(server, path + "/history", cookie=bob)[1]["history"][-1]["revision"] == 2


def test_migration_preserves_saved_preferences_and_deleted_recipient_can_be_reassigned(tmp_path):
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as conn:
        for script in MIGRATIONS[:8]:
            conn.executescript(script)
        conn.execute("PRAGMA user_version = 8")
        conn.execute("INSERT INTO users VALUES (1,'alice','not-a-real-hash','now')")
        conn.execute("INSERT INTO personal_prompts (id,owner_id,title,domain_key,prompt,created_at,updated_at) VALUES ('old',1,'기존','coding','기존 지침','now','now')")
    db = Database(path)
    store = HandoffStore(db)
    assert store.list_for(1) == []
    assert PersonalPromptStore(db).get(1, "old")["prompt"] == "기존 지침"
    bob, _ = AuthService(db).signup("bob", "bob-password-123")
    carol, _ = AuthService(db).signup("carol", "carol-password-123")
    item = store.create(1, BODY)
    store.change(1, item["id"], "share", {"username": "bob", "revision": 1})
    store.change(bob.id, item["id"], "claim", {"revision": 2})
    with db.connect() as conn:
        conn.execute("DELETE FROM users WHERE id=?", (bob.id,))
    assert store.get(1, item["id"])["can_share"]
    store.change(1, item["id"], "share", {"username": "carol", "revision": 3})
    assert store.get(carol.id, item["id"])["status"] == "shared"
    with db.connect() as conn:
        conn.execute("DELETE FROM users WHERE id=1")
        assert conn.execute("SELECT COUNT(*) FROM handoff_versions").fetchone()[0] == 0
