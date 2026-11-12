import copy
from itertools import product
import json
import sqlite3

import pytest

import api_server
from app_db import Database, MIGRATIONS
from auth import AuthService
from coding_instructions import build_coding_instructions, PREFERENCES
from personal_prompts import PersonalPromptStore, PromptConflict
from tests.test_personal_prompts import request, signup
from tests.test_team import db, server

PROFILE = {"language": "Python", "framework": "FastAPI", "preferences": {
    "explanation": "steps", "comments": "essential", "structure": "modular", "output": "changes",
}, "extra": "한국어로 설명하고 기존 함수 이름은 유지"}


@pytest.mark.parametrize("language,framework", [("Python", "FastAPI"), ("Java", "Spring Boot"), ("C++", ""), ("Elixir", "Phoenix 1.x"), ("TypeScript", "React")])
def test_selected_environment_is_preserved_without_unrelated_react_rules(language, framework):
    profile = {**PROFILE, "language": language, "framework": framework}
    draft = build_coding_instructions(profile)
    assert draft["profile"] == profile
    assert f"개발 언어: {language}" in draft["prompt"]
    assert (framework or "별도 지정 없음") in draft["prompt"]
    assert "useState" not in draft["prompt"] and "TSX" not in draft["prompt"]
    assert "예시 비교로 추정한 결과가 아니다" in draft["prompt"]
    assert PROFILE["extra"] in draft["prompt"]


def test_every_preference_combination_is_distinct_and_does_not_mutate_input():
    prompts = set()
    for values in product(*(tuple(options) for options in PREFERENCES.values())):
        profile = {**PROFILE, "preferences": dict(zip(PREFERENCES, values))}
        before = copy.deepcopy(profile)
        draft = build_coding_instructions(profile)
        assert profile == before
        for key, options in PREFERENCES.items():
            assert options[profile["preferences"][key]] in draft["prompt"]
            assert all(text not in draft["prompt"] for value, text in options.items() if value != profile["preferences"][key])
        prompts.add(draft["prompt"])
    assert len(prompts) == 16


@pytest.mark.parametrize("changes", [
    {"language": " "}, {"language": ["Python"]}, {"language": "a" * 61}, {"language": "Python\nJava"},
    {"framework": "a" * 101}, {"framework": "Fast\tAPI"}, {"extra": "a" * 1001},
    {"preferences": []}, {"preferences": {}}, {"preferences": {**PROFILE["preferences"], "comments": "fake"}},
    {"preferences": {**PROFILE["preferences"], "other": "private"}}, {"preferences": {**PROFILE["preferences"], "comments": []}},
])
def test_invalid_profiles_are_rejected(changes):
    with pytest.raises(ValueError):
        build_coding_instructions({**PROFILE, **changes})


def test_saved_profile_survives_restart_and_manual_edits_are_not_reinterpreted(db):
    user, _ = AuthService(db).signup("alice", "alice-password-123")
    store = PersonalPromptStore(db)
    draft = build_coding_instructions(PROFILE)
    body = {"title": "Python 방식", "domainKey": "coding", "prompt": draft["prompt"], "codingProfile": PROFILE}
    item = store.create(user.id, body)
    assert item["coding_profile"] == PROFILE and item["coding_profile_matches"] is True
    assert PersonalPromptStore(Database(db.path)).get(user.id, item["id"]) == item
    listed = store.list_for(user.id)[0]
    assert listed["coding_environment"] == {"language": "Python", "framework": "FastAPI"}
    assert "한국어로" not in json.dumps(listed, ensure_ascii=False) and "prompt" not in listed
    renamed = store.update(user.id, item["id"], {**body, "title": "이름 수정", "revision": 1})
    assert renamed["coding_profile_matches"] is True
    edited = store.update(user.id, item["id"], {**body, "prompt": "수동으로 고친 내용", "revision": 2,
        "codingProfile": {**PROFILE, "language": "Java"}})
    assert edited["coding_profile"] == PROFILE and edited["coding_profile_matches"] is False
    with pytest.raises(PromptConflict):
        store.update(user.id, item["id"], {**body, "revision": 1})
    for bad in ({"prompt": "위조"}, {"domainKey": "summarization_ko"}, {"codingProfile": {}}):
        with pytest.raises(ValueError):
            store.create(user.id, {**body, **bad})


def test_migration_preserves_existing_react_prompt(tmp_path):
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as conn:
        for script in MIGRATIONS[:7]:
            conn.executescript(script)
        conn.execute("PRAGMA user_version = 7")
        conn.execute("INSERT INTO users VALUES (1, 'alice', 'not-a-real-hash', 'now')")
        conn.execute("INSERT INTO personal_prompts (id,owner_id,title,domain_key,prompt,created_at,updated_at) VALUES ('react',1,'기존 React','coding','기존 본문','now','now')")
    database = Database(path)
    item = PersonalPromptStore(database).get(1, "react")
    assert item["prompt"] == "기존 본문" and item["revision"] == 1 and item["coding_profile"] is None
    with database.connect() as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == len(MIGRATIONS)


def test_preview_save_reopen_and_reuse_never_silently_apply_react_team_rules(server, monkeypatch):
    monkeypatch.setattr(api_server, "_take", lambda *_: pytest.fail("조립·저장·잘못된 팀 적용은 모델 사용량을 차감하지 않는다"))
    monkeypatch.setattr(api_server.service.generator, "generate_with_prompt", lambda *_args, **_kwargs: pytest.fail("미리 보기와 저장은 모델을 호출하지 않는다"))
    status, data, _ = request(server, "/coding-instructions/preview", {"profile": PROFILE, "sourceText": "PRIVATE TASK"})
    assert status == 200 and "PRIVATE TASK" not in json.dumps(data)
    draft = data["draft"]
    body = {"title": "FastAPI 지침", "domainKey": "coding", "prompt": draft["prompt"], "codingProfile": draft["profile"]}
    assert request(server, "/coding-instructions/preview", {"profile": {}})[0] == 400
    assert request(server, "/preferences", body)[0] == 401
    cookie = signup(server, "alice")
    status, data, _ = request(server, "/preferences", body, cookie)
    assert status == 201
    item = data["preference"]
    path = f"/preferences/{item['id']}"
    assert request(server, path, cookie=cookie)[1]["preference"] == item
    bob = signup(server, "bob")
    assert request(server, path, cookie=bob)[0] == 404
    for action in ("compare-team", "compose-task", "save-task"):
        assert request(server, path + "/" + action, {"revision": 1, "teamCode": "devteam"}, cookie)[0] == 400
    for basis in ("team", "custom"):
        assert request(server, path + "/run", {"revision": 1, "basis": basis, "task": "새 요청"}, cookie)[0] == 400
    monkeypatch.setattr(api_server, "LIVE", True)
    monkeypatch.setattr(api_server, "_live_key_available", lambda _: True)
    monkeypatch.setattr(api_server, "_take", lambda *_: None)
    seen = []
    monkeypatch.setattr(api_server.service.generator, "generate_with_prompt", lambda prompt, task, model: seen.append((prompt, task)) or "가상 결과")
    assert request(server, path + "/run", {"revision": 1, "basis": "personal", "task": "다음 작업 자료"}, cookie)[0] == 200
    assert seen == [(draft["prompt"], "다음 작업 자료")]
    assert request(server, path, cookie=cookie)[1]["preference"] == item
