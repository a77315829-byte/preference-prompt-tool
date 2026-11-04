"""팀 생성부터 초대 확인·선호 반영까지. 모델 API는 호출하지 않는다."""
import pytest

import api_server
import app_db
import team
from app_db import Database
from auth import AuthService
from tests.test_team import _call, _finished_session, _history, db, server


def test_create_empty_team_persists_name_and_uses_existing_limits(db, monkeypatch):
    monkeypatch.setattr(team, "MAX_ANON_TEAMS", 1)
    store = team.TeamStore(db)
    code = store.create("우리 개발팀", "coding")
    assert store.get(code) == ("coding", [])
    assert team.TeamStore(Database(db.path)).name_for(code) == "우리 개발팀"
    with pytest.raises(team.TeamError, match="로그인"):
        store.create("다른 팀", "coding")
    store.add(code, "coding", "민수", _history("coding", {}), require_existing=True)
    assert len(store.get(code)[1]) == 1


def test_creator_can_find_empty_team_without_a_preference_vote(db):
    user, _ = AuthService(db).signup("alice", "alice-password-1")
    store = team.TeamStore(db)
    code = store.create("프론트엔드팀", "coding", user.id)
    summary, = store.list_for_user(user.id)
    assert (summary.code, summary.name, summary.members) == (code, "프론트엔드팀", 0)


def test_migration_keeps_legacy_team_and_preferences(tmp_path, monkeypatch):
    original = list(app_db.MIGRATIONS)
    monkeypatch.setattr(app_db, "MIGRATIONS", original[:4])
    path = tmp_path / "legacy.db"
    old = Database(path)
    with old.connect() as conn:
        conn.execute("INSERT INTO teams (code, domain_key, created_at) VALUES ('legacy', 'coding', '2026-11-03')")
        conn.execute("INSERT INTO team_members (code, member_key, name, history_json, joined_at) VALUES ('legacy', 'name:a', 'a', '[]', '2026-11-03')")
    monkeypatch.setattr(app_db, "MIGRATIONS", original)
    store = team.TeamStore(Database(path))
    assert store.name_for("legacy") == "legacy"
    assert [m.name for m in store.get("legacy")[1]] == ["a"]


def test_invitation_never_recreates_a_missing_team(db):
    store = team.TeamStore(db)
    with pytest.raises(team.TeamError, match="초대한 팀"):
        store.add("missing-team", "coding", "민수", _history("coding", {}), require_existing=True)
    with pytest.raises(team.TeamError):
        store.get("missing-team")


def test_create_preview_compare_and_explicitly_merge(server):
    status, data = _call(server, "/teams", {"name": "프론트엔드팀", "domainKey": "coding"})
    assert status == 201
    created = data["team"]
    assert created["name"] == "프론트엔드팀"
    assert created["members"] == [] and created["prompt"] == "" and created["exports"] == []
    code = created["code"]
    assert _call(server, f"/teams/{code}")[1]["team"]["members"] == []
    session_id = _finished_session(server, "a")
    # 초대를 보거나 비교만 마쳐도 아직 팀에는 반영되지 않는다.
    assert _call(server, f"/teams/{code}")[1]["team"]["members"] == []
    status, data = _call(server, f"/teams/{code}/members", {
        "sessionId": session_id, "name": "민수", "requireExisting": True,
    })
    assert status == 200
    assert data["team"]["members"] == ["민수"] and data["team"]["prompt"]
    assert data["team"]["name"] == "프론트엔드팀"
    assert _call(server, "/teams/expired-invite/members", {
        "sessionId": session_id, "name": "민수", "requireExisting": True,
    })[0] == 400


def test_create_validates_name_domain_and_mismatched_comparisons(server):
    for body in ({"name": " ", "domainKey": "coding"}, {"name": "a" * 61},
                 {"name": "팀", "domainKey": "idle_tracker"}):
        assert _call(server, "/teams", body)[0] == 400
    _, data = _call(server, "/teams", {"name": "요약팀", "domainKey": "summarization_ko"})
    code = data["team"]["code"]
    assert _call(server, f"/teams/{code}/members", {
        "sessionId": _finished_session(server, "a"), "name": "민수", "requireExisting": True,
    })[0] == 400
    assert _call(server, f"/teams/{code}")[1]["team"]["members"] == []
