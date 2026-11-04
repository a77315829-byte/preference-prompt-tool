import json

from auth import AuthService
from personal_prompts import PersonalPromptStore
from tests.test_team import db


def test_lineage_summary_preserves_parent_identity_and_hides_prompt_details(db):
    user, _ = AuthService(db).signup("alice", "alice-password-123")
    other, _ = AuthService(db).signup("bob", "bob-password-123")
    store = PersonalPromptStore(db)
    body = {"title": "원래 작업용", "domainKey": "coding", "prompt": "PRIVATE PROMPT"}
    root = store.create(user.id, body, provenance={"operation": "task"})
    parent = {"id": root["id"], "title": root["title"], "revision": 1, "axes": [{"value": "PRIVATE AXIS"}]}
    child = store.create(user.id, {**body, "title": "새 조합"}, provenance={"operation": "remix", "remixed_from": parent})
    restored = store.create(user.id, {**body, "title": "일부 되돌림"}, provenance={"operation": "restore", "remixed_from": {"id": child["id"], "title": child["title"], "revision": 1}})
    store.create(other.id, {**body, "title": "다른 계정 항목"})
    listing = {i["id"]: i for i in store.list_for(user.id)}
    assert listing[root["id"]]["lineage"] == {"kind": "task", "parent": None}
    assert listing[child["id"]]["lineage"]["parent"] == {k: parent[k] for k in ("id", "title", "revision")}
    assert listing[restored["id"]]["lineage"]["kind"] == "restore"
    assert "PRIVATE" not in json.dumps(listing) and "다른 계정" not in json.dumps(listing, ensure_ascii=False)
    renamed = store.update(user.id, root["id"], {**body, "title": "고친 원래 작업용", "revision": 1})
    assert renamed["revision"] == 2
    assert store.get(user.id, child["id"])["provenance"]["remixed_from"] == parent
    store.delete(user.id, root["id"], 2)
    assert store.list_for(user.id)[-1]["lineage"]["parent"]["id"] == root["id"]


def test_legacy_links_are_not_inferred_and_request_body_cannot_forge_them(db):
    user, _ = AuthService(db).signup("alice", "alice-password-123")
    store = PersonalPromptStore(db)
    body = {"title": "같은 이름", "domainKey": "coding", "prompt": "지침"}
    direct = store.create(user.id, {**body, "provenance": {"operation": "remix", "remixed_from": {"id": "fake"}}})
    legacy = store.create(user.id, body, provenance={"remixed_from": {"title": body["title"], "revision": 1}})
    listing = {i["id"]: i for i in store.list_for(user.id)}
    assert listing[direct["id"]]["lineage"] == {"kind": "personal", "parent": None}
    assert listing[legacy["id"]]["lineage"] == {"kind": "derived", "parent": {"title": body["title"], "revision": 1}}
