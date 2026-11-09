"""Model-free team/export/real-work workflow, access control and measurement integrity."""
import copy
import json
import sqlite3

import pytest

import api_server
from app_db import Database, MIGRATIONS
from auth import AuthService
from coding_team_guides import CodingTeamGuides
from coding_work_exports import BEGIN, END, export_preview
from coding_work_trials import CodingWorkTrials
from personal_prompts import PersonalPromptStore, PromptConflict
from tests.test_team import db, server
from tests.test_personal_prompts import request, signup

PROFILE = {"language": "TypeScript", "framework": "React", "extra": "개인 메모",
           "preferences": {"explanation": "brief", "comments": "essential", "structure": "compact", "output": "changes"}}
TASK = {"title": "검색 초기화 버그", "task": "검색어를 지우면 전체 목록을 다시 표시하세요.",
        "tool": "사용자 도구", "model": "같은 모델·설정", "context": "기준 커밋 abc123, 기존 규칙 동일, 타입/회귀 검사·화면 확인"}


@pytest.fixture
def accounts(db):
    auth = AuthService(db)
    return [auth.signup(name, name + "-password-123")[0] for name in ("alice", "bob", "carol")]


def test_upgrade_from_13_preserves_existing_team(tmp_path):
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as conn:
        for script in MIGRATIONS[:13]:
            conn.executescript(script)
        conn.execute("PRAGMA user_version=13")
        conn.execute("INSERT INTO teams(code,domain_key,created_at,name) VALUES ('old','coding','now','기존')")
    with Database(path).connect() as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == len(MIGRATIONS)
        assert conn.execute("SELECT name FROM teams WHERE code='old'").fetchone()[0] == "기존"
        assert conn.execute("SELECT COUNT(*) FROM coding_work_trials").fetchone()[0] == 0


def test_team_privacy_explicit_choices_revision_and_frozen_provenance(db, accounts):
    alice, bob, carol = accounts
    guides = CodingTeamGuides(db)
    team = guides.create(alice, "프론트", PROFILE, ["공개 API 유지"])
    assert "extra" not in team["profile"] and "개인 메모" not in team["prompt"]
    with pytest.raises(PermissionError):
        guides.get(team["code"], bob.id)
    guides.join(bob, team["code"])
    with pytest.raises(PermissionError):
        guides.update(bob.id, team["code"], 1, PROFILE, [])
    other = copy.deepcopy(PROFILE)
    other["preferences"]["structure"] = "modular"
    choice = {"code": team["code"], "revision": 1, "choices": {"structure": "team"}}
    with pytest.raises(ValueError, match="다른 항목"):
        guides.resolve(bob.id, other, {**choice, "choices": {}})
    with pytest.raises(ValueError, match="언어"):
        guides.resolve(bob.id, {**other, "language": "JavaScript"}, choice)
    draft = guides.resolve(bob.id, other, choice)
    assert draft["profile"]["preferences"]["structure"] == "compact"
    store = PersonalPromptStore(db)
    saved = store.create(bob.id, {"title": "작업용", "domainKey": "coding", "prompt": draft["prompt"],
                                 "codingProfile": draft["profile"]}, team_context=draft["team_context"])
    assert saved["coding_profile_matches"]
    guides.update(alice.id, team["code"], 1, PROFILE, ["새 규칙"])
    with pytest.raises(PromptConflict):
        guides.resolve(bob.id, other, choice)
    restored = store.get(bob.id, saved["id"])
    assert restored["coding_team_context"]["rules"] == ["공개 API 유지"]
    assert restored["coding_team_context"]["source_profile"]["preferences"]["structure"] == "modular"
    with db.connect() as conn:
        conn.execute("UPDATE teams SET invite_until=0 WHERE code=?", (team["code"],))
    assert guides.join(bob, team["code"])["is_member"]
    with pytest.raises(PermissionError, match="초대"):
        guides.join(carol, team["code"])


@pytest.mark.parametrize("target,path", [("agents_md", "AGENTS.md"), ("claude_code", "CLAUDE.md"),
                                        ("copilot", ".github/copilot-instructions.md"), ("markdown", None)])
def test_exports_preserve_user_text_and_replace_only_managed_block(target, path):
    existing = "  # 팀 기존 규칙\n키를 남기지 않는다.\n\n"
    first = export_preview({"prompt": "첫 지침", "target": target, "existing": existing})
    assert first["content"].startswith(existing) and first["diff"]
    if path:
        assert first["path"] == path
    original = first["content"] + "\n후기 규칙\n  "
    updated = export_preview({"prompt": "새 지침", "target": target, "existing": original})
    assert updated["content"].startswith(existing) and updated["content"].endswith("\n후기 규칙\n  ")
    assert updated["content"].count(BEGIN) == 1 and "첫 지침" not in updated["content"]
    assert export_preview({"prompt": "새 지침", "target": target, "existing": updated["content"]})["diff"] == ""


def test_exports_reject_damaged_markers_and_cursor_existing_scope():
    for existing in (BEGIN, END + BEGIN, BEGIN + BEGIN + END):
        with pytest.raises(ValueError):
            export_preview({"prompt": "안내", "existing": existing})
    with pytest.raises(ValueError, match="적용 범위"):
        export_preview({"prompt": "안내", "target": "cursor", "existing": "alwaysApply: false"})
    assert "alwaysApply: true" in export_preview({"prompt": "안내", "target": "cursor"})["content"]


def test_trials_server_timing_restart_independent_metrics_and_owner_access(db, accounts):
    alice, bob, _ = accounts
    clock = [100.0]
    store = CodingWorkTrials(db, clock=lambda: clock[0])
    guides = CodingTeamGuides(db)
    team = guides.create(alice, "팀", PROFILE, ["동일 필수 규칙"])
    draft = guides.resolve(alice.id, PROFILE, {"code": team["code"], "revision": 1, "choices": {}})
    trial = store.create(alice.id, TASK, draft)
    original = copy.deepcopy(trial["prompts"])
    assert trial["comparison"]["seconds"] == {"general": None, "selected": None}
    assert trial["prompts"]["general"].split("## 이번 작업의 팀 필수 규칙")[1] == trial["prompts"]["selected"].split("## 이번 작업의 팀 필수 규칙")[1]
    assert "## 직접 고른 내 작성 선호" not in trial["prompts"]["general"]
    with pytest.raises(LookupError):
        store.get(bob.id, trial["id"])

    def change(action, **values):
        nonlocal trial
        trial = store.change(alice.id, trial["id"], {"revision": trial["revision"], **values}, action)

    change("timer", operation="start", arm="general", phase="setup")
    second = store.create(alice.id, TASK, draft)
    with pytest.raises(ValueError, match="다른 작업"):
        store.change(alice.id, second["id"], {"revision": 1, "operation": "start", "arm": "selected", "phase": "edit"}, "timer")
    clock[0] += 12
    store = CodingWorkTrials(Database(db.path), clock=lambda: clock[0])
    assert store.get(alice.id, trial["id"])["active"]["since"] == 100.0
    change("timer", operation="pause")
    for arm, phase, seconds in (("general", "edit", 48), ("selected", "setup", 20), ("selected", "edit", 30)):
        change("timer", operation="start", arm=arm, phase=phase)
        clock[0] += seconds
        change("timer", operation="pause")
    assert trial["comparison"]["seconds_saved"] == 10
    assert trial["comparison"]["edit_seconds_saved"] == 18
    assert trial["comparison"]["edit_seconds"] == {"general": 48, "selected": 30}
    assert not trial["comparison"]["both_checked"]
    with pytest.raises(PromptConflict):
        store.change(alice.id, trial["id"], {"revision": 1}, "delete")
    with pytest.raises(ValueError, match="근거"):
        change("result", arm="selected", outcome="pass")
    with pytest.raises(ValueError, match="전체 통과"):
        change("result", arm="selected", outcome="pass", evidence="테스트", passed_tests=1, total_tests=2)
    change("result", arm="general", outcome="pass", evidence="관련 테스트 4/4, 화면 재현 해결", passed_tests=4, total_tests=4)
    change("result", arm="selected", outcome="fail", evidence="회귀 1개 실패", passed_tests=3, total_tests=4)
    change("preference", preference="selected", reason="더 읽기 쉬움, 기능 오류는 별도")
    assert trial["comparison"]["both_checked"] and not trial["comparison"]["both_passed"]
    assert trial["preference"] == "selected" and trial["prompts"] == original
    assert store.list(bob.id) == []
    change("delete")
    assert trial is None


def test_api_complete_path_membership_saved_snapshot_and_account_cleanup(server):
    alice, bob, outsider = [signup(server, name) for name in ("alice", "bob", "outsider")]
    base = "/coding-work/"
    assert request(server, base + "trials")[0] == 401
    status, data, _ = request(server, base + "teams", {"name": "React 팀", "profile": PROFILE, "rules": ["기존 타입 유지"]}, alice)
    assert status == 201, data
    team = data["team"]
    code = team["code"]
    assert request(server, "/teams/" + code, cookie=outsider)[1]["team"]["requires_join"]
    assert request(server, base + "teams/" + code, cookie=outsider)[0] == 403
    assert request(server, base + f"teams/{code}/join", {}, bob)[0] == 200
    assert request(server, "/teams", cookie=bob)[1]["teams"][0]["domain_key"] == "coding_profile"
    source = {"profile": PROFILE, "teamSelection": {"code": code, "revision": 1, "choices": {}}}
    status, data, _ = request(server, base + "resolve", source, bob)
    assert status == 200, data
    draft = data["draft"]
    assert request(server, base + "save", {**source, "title": "틀린 스냅샷", "snapshot": "stale"}, bob)[0] == 409
    status, data, _ = request(server, base + "save", {**source, "title": "팀 작업용", "snapshot": draft["snapshot"]}, bob)
    assert status == 201, data
    item = data["preference"]
    assert item["coding_team_context"]["code"] == code and item["coding_profile_matches"]
    saved_source = {"preferenceId": item["id"], "preferenceRevision": item["revision"]}
    stored = request(server, base + "resolve", saved_source, bob)[1]["draft"]
    status, data, _ = request(server, base + "trials", {**saved_source, **TASK, "snapshot": stored["snapshot"]}, bob)
    assert status == 201, data
    trial = data["trial"]
    assert request(server, base + "trials/" + trial["id"], cookie=alice)[0] == 404
    assert request(server, base + "exports", {"prompt": draft["prompt"], "target": "claude_code"})[0] == 200
    status, data, _ = request(server, "/teams/" + code + "/invitation", {"enabled": False}, alice)
    assert status == 200, data
    assert request(server, base + f"teams/{code}/join", {}, outsider)[0] == 403
    assert request(server, "/auth/delete", {"password": "bob-password-123"}, bob)[0] == 200
    with api_server.DB.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM coding_work_trials").fetchone()[0] == 0
