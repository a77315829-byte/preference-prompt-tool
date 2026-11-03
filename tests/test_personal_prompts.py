import json
import urllib.error
import urllib.request

import pytest

import api_server
import personal_prompts
from auth import AuthService
from budget import DailyBudget
from personal_prompts import PersonalPromptStore, PromptConflict
from tests.test_team import db, server

BODY = {"title": "짧은 회의록", "domainKey": "summarization_ko", "prompt": "결정 사항과 할 일을 짧게 요약하라.", "note": "팀 회의 후"}


def request(base, path, body=None, cookie=None):
    headers = {"Content-Type": "application/json"}
    if cookie:
        headers["Cookie"] = cookie
    req = urllib.request.Request(base + path, data=None if body is None else json.dumps(body).encode(), headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read()), resp.headers
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read()), exc.headers


def signup(base, name):
    status, _, headers = request(base, "/auth/signup", {"username": name, "password": f"{name}-password-123"})
    assert status == 200
    return headers["Set-Cookie"].split(";")[0]


def test_store_survives_restart_and_prevents_stale_writes(db, monkeypatch):
    user, _ = AuthService(db).signup("alice", "alice-password-123")
    store = PersonalPromptStore(db)
    item = store.create(user.id, BODY)
    restored = PersonalPromptStore(type(db)(db.path)).get(user.id, item["id"])
    assert restored["prompt"] == BODY["prompt"]
    updated = store.update(user.id, item["id"], {**BODY, "prompt": "새 지침", "revision": 1})
    assert updated["revision"] == 2
    with pytest.raises(PromptConflict):
        store.update(user.id, item["id"], {**BODY, "revision": 1})
    with pytest.raises(PromptConflict):
        store.delete(user.id, item["id"], 1)
    monkeypatch.setattr(personal_prompts, "MAX_PROMPTS", 1)
    with pytest.raises(ValueError, match="1개"):
        store.create(user.id, BODY)


@pytest.mark.parametrize("changes", [{"title": " "}, {"prompt": ""}, {"prompt": "a" * 20001}, {"note": "a" * 1001}, {"domainKey": "idle_tracker"}])
def test_invalid_content_is_not_stored(db, changes):
    user, _ = AuthService(db).signup("alice", "alice-password-123")
    store = PersonalPromptStore(db)
    with pytest.raises(ValueError):
        store.create(user.id, {**BODY, **changes})
    assert store.list_for(user.id) == []


def test_api_create_edit_list_delete_and_isolate_accounts(server):
    alice = signup(server, "alice")
    bob = signup(server, "bob")
    assert request(server, "/preferences")[0] == 401
    assert request(server, "/preferences", BODY)[0] == 401
    status, data, _ = request(server, "/preferences", {**BODY, "source_text": "PRIVATE SOURCE"}, alice)
    assert status == 201
    item = data["preference"]
    path = f"/preferences/{item['id']}"
    assert "PRIVATE SOURCE" not in json.dumps(data)
    status, data, _ = request(server, "/preferences", cookie=alice)
    assert status == 200 and data["preferences"][0]["title"] == BODY["title"]
    assert "prompt" not in data["preferences"][0]
    assert request(server, "/preferences", cookie=bob)[1]["preferences"] == []
    for action, body in [("", None), ("/update", {**BODY, "revision": 1}), ("/delete", {"revision": 1}), ("/run", {"revision": 1, "task": "비공개"})]:
        assert request(server, path + action, body, bob)[0] == 404
    status, data, _ = request(server, path + "/update", {**BODY, "title": "변경한 이름", "prompt": "수정 지침", "revision": 1}, alice)
    assert status == 200 and data["preference"]["revision"] == 2
    assert request(server, path + "/update", {**BODY, "revision": 1}, alice)[0] == 409
    assert request(server, path + "/delete", {"revision": 1}, alice)[0] == 409
    assert request(server, path + "/delete", {"revision": 2}, alice)[0] == 200
    assert request(server, path, cookie=alice)[0] == 404


def test_account_deletion_removes_personal_prompts(server):
    cookie = signup(server, "alice")
    _, data, _ = request(server, "/preferences", BODY, cookie)
    item_id = data["preference"]["id"]
    assert request(server, "/auth/delete", {"password": "alice-password-123"}, cookie)[0] == 200
    with api_server.DB.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM personal_prompts WHERE id = ?", (item_id,)).fetchone()[0] == 0


@pytest.mark.parametrize("domain", ["coding", "summarization_ko"])
def test_reuse_executes_saved_revision_with_server_model_only(server, monkeypatch, domain):
    cookie = signup(server, "alice")
    _, data, _ = request(server, "/preferences", {**BODY, "domainKey": domain}, cookie)
    item = data["preference"]
    path = f"/preferences/{item['id']}/run"
    monkeypatch.setattr(api_server, "LIVE", False)
    assert request(server, path, {"revision": 1, "task": "새 작업"}, cookie)[0] == 400
    seen = []
    monkeypatch.setattr(api_server, "LIVE", True)
    monkeypatch.setattr(api_server, "_live_key_available", lambda _: True)
    monkeypatch.setattr(api_server, "DAILY_PREFERENCE_RUNS", DailyBudget(1))
    monkeypatch.setattr(api_server.service.generator, "generate_with_prompt", lambda prompt, source, model: seen.append((prompt, source, model)) or "실행 결과")
    for bad in ({"revision": 2, "task": "새 작업"}, {"revision": 1, "task": " "}, {"revision": 1, "task": "x" * 12001}):
        assert request(server, path, bad, cookie)[0] in (400, 409)
    assert seen == []
    status, data, _ = request(server, path, {"revision": 1, "task": "새 작업", "model": "client-expensive-model"}, cookie)
    expected = api_server.CODING_MODEL if domain == "coding" else api_server.DEFAULT_MODEL
    assert status == 200 and data["output"] == "실행 결과"
    assert seen == [(BODY["prompt"], "새 작업", expected)]
    assert request(server, path, {"revision": 1, "task": "또 다른 작업"}, cookie)[0] == 400
    assert len(seen) == 1


def test_provider_error_does_not_expose_keys_or_change_saved_prompt(server, monkeypatch):
    cookie = signup(server, "alice")
    _, data, _ = request(server, "/preferences", BODY, cookie)
    item = data["preference"]
    monkeypatch.setattr(api_server, "LIVE", True)
    monkeypatch.setattr(api_server, "_live_key_available", lambda _: True)
    monkeypatch.setattr(api_server, "DAILY_PREFERENCE_RUNS", DailyBudget(1))
    def fail(*_, **__):
        raise RuntimeError("Incorrect API key provided: sk-private-secret")
    monkeypatch.setattr(api_server.service.generator, "generate_with_prompt", fail)
    status, data, _ = request(server, f"/preferences/{item['id']}/run", {"revision": 1, "task": "새 작업"}, cookie)
    assert status == 502 and "sk-private" not in json.dumps(data)
    assert request(server, f"/preferences/{item['id']}", cookie=cookie)[1]["preference"]["prompt"] == BODY["prompt"]
