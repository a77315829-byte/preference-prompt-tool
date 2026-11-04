import copy

import app_db
import api_server
import team
from auth import AuthService
from engine.domain_loader import load_domain
from engine.generator import build_final_prompt
from personal_prompts import PersonalPromptStore
from preference_comparison import compare_preferences, compose_task_prompt
from tests.test_personal_prompts import BODY, request
from tests.test_preference_comparison import COMBO, prepare
from tests.test_team import _history, server


def test_migration_keeps_existing_items_without_guessing_sources(tmp_path, monkeypatch):
    migrations = app_db.MIGRATIONS
    monkeypatch.setattr(app_db, "MIGRATIONS", migrations[:6])
    db = app_db.Database(tmp_path / "legacy.db")
    user, _ = AuthService(db).signup("alice", "alice-password-123")
    with db.connect() as conn:
        conn.execute("INSERT INTO personal_prompts (id, owner_id, title, domain_key, prompt, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                     ("old", user.id, BODY["title"], BODY["domainKey"], BODY["prompt"], "then", "then"))
    monkeypatch.setattr(app_db, "MIGRATIONS", migrations)
    restored = app_db.Database(db.path)
    item = PersonalPromptStore(restored).get(user.id, "old")
    assert item["prompt"] == BODY["prompt"] and item["revision"] == 1
    assert item["provenance"] is None and item["provenance_matches"] is None
    with restored.connect() as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == len(migrations)


def test_sources_include_personal_team_shared_and_undecided_selection():
    domain = load_domain("domains/coding.yaml")
    personal = {**COMBO, "code_structure": ""}
    item = {"id": "p", "revision": 3, "title": "개인 방식", "prompt": build_final_prompt(domain, personal)}
    members = [team.Member("팀원", _history("coding", {**COMBO, "code_structure": "separated", "type_detail": "inferred"}))]
    comparison = compare_preferences(item, domain, "devteam", "개발팀", members)
    draft = compose_task_prompt(item, domain, comparison, {"code_structure": "personal", "type_detail": "team"})
    rows = {r["axis"]: r for r in draft["provenance"]["axes"]}
    assert rows["code_structure"]["source"] == "personal" and rows["code_structure"]["value"] == ""
    assert rows["type_detail"]["source"] == "team" and rows["type_detail"]["value"] == "inferred"
    assert rows["style_management"]["source"] == "shared" and rows["style_management"]["value"] == "theme"
    assert draft["provenance"]["personal"] == {"title": "개인 방식", "revision": 3}
    assert draft["provenance"]["team"] == {"name": "개발팀"}


def test_saved_sources_are_server_derived_and_survive_source_changes_and_edits(server):
    cookie, original, path = prepare(server)
    api_server.TEAMS.add("devteam", "coding", "민수", _history("coding", {**COMBO, "code_structure": "separated"}))
    before_team = copy.deepcopy(api_server.TEAMS.get("devteam"))
    _, data, _ = request(server, path + "/compare-team", {"revision": 1, "teamCode": "devteam"}, cookie)
    comparison = data["comparison"]
    body = {"revision": 1, "teamCode": "devteam", "teamSnapshot": comparison["team_snapshot"],
            "language": comparison["team_language"], "choices": {"code_structure": "team"}}
    _, data, _ = request(server, path + "/compose-task", body, cookie)
    status, data, _ = request(server, path + "/save-task", {**body, "taskSnapshot": data["draft"]["snapshot"],
        "title": "작업용", "provenance": {"team": {"name": "조작된 팀"}}, "task": "PRIVATE TASK"}, cookie)
    assert status == 201
    saved = data["preference"]
    origin = saved["provenance"]
    assert saved["provenance_matches"] is True and "PRIVATE TASK" not in str(origin)
    assert origin["personal"]["title"] == original["title"]
    assert origin["team"]["name"] == comparison["team_name"]
    assert {a["axis"]: a["source"] for a in origin["axes"]} == {"code_structure": "team", "style_management": "shared", "type_detail": "shared"}
    assert api_server.PERSONAL_PROMPTS.get(1, original["id"]) == original
    assert api_server.TEAMS.get("devteam") == before_team
    # 이름과 설명만 수정하면 현재 지침에도 기록이 유효하다.
    fields = {"title": "새 이름", "note": "새 설명", "domainKey": saved["domain_key"], "prompt": saved["prompt"], "revision": 1}
    status, data, _ = request(server, f"/preferences/{saved['id']}/update", {**fields, "provenance": {}}, cookie)
    assert status == 200 and data["preference"]["provenance_matches"] is True
    assert data["preference"]["provenance"] == origin
    # 원본 삭제·팀 변경·DB 재시작 후에도 저장 당시 기록은 유지한다.
    api_server.PERSONAL_PROMPTS.delete(1, original["id"], 1)
    api_server.TEAMS.add("devteam", "coding", "민수", _history("coding", COMBO))
    restored = PersonalPromptStore(app_db.Database(api_server.DB.path)).get(1, saved["id"])
    assert restored["provenance"] == origin and restored["provenance_matches"] is True
    status, data, _ = request(server, f"/preferences/{saved['id']}/update", {**fields, "revision": 2, "prompt": "직접 수정한 지침"}, cookie)
    assert status == 200 and data["preference"]["provenance_matches"] is False
    assert data["preference"]["provenance"] == origin
    status, data, _ = request(server, f"/preferences/{saved['id']}/update", {**fields, "revision": 3, "domainKey": "summarization_ko"}, cookie)
    assert status == 200 and data["preference"]["provenance_matches"] is False


def test_generic_create_cannot_forge_source_records(tmp_path):
    db = app_db.Database(tmp_path / "private.db")
    user, _ = AuthService(db).signup("alice", "alice-password-123")
    saved = PersonalPromptStore(db).create(user.id, {**BODY, "provenance": {"team": {"name": "fake"}}})
    assert saved["provenance"] is None
