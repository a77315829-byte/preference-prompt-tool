"""다시 열기 · 답 보완 · 버전 (prompt_workspace/questions.py, store.py) 와 그 API.

고정하는 것: 답은 사용자가 고른 곳으로만 들어간다, 저장은 덮어쓰지 않고 쌓인다,
복원도 새 버전이다, 남의 프로젝트는 보이지도 열리지도 않는다, 예전 프로젝트도 열린다."""

from __future__ import annotations

import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

import api_server
from app_db import Database
from auth import AuthService
from prompt_workspace import builder, questions
from prompt_workspace.examples import synthetic_cost
from prompt_workspace.models import ProjectError, new_project, status, validate_project
from prompt_workspace.store import ProjectStore


def _sample() -> dict:
    project = new_project("샘플", synthetic_cost.SAMPLE_DESCRIPTION)
    project["requirements"] = synthetic_cost.sample_requirements()
    project["check_set"] = synthetic_cost.NAME
    return validate_project(project)


# --- answers ------------------------------------------------------------------


def test_answer_becomes_a_rule_and_the_question_is_kept_as_history() -> None:
    project = questions.resolve(_sample(), "Q1", "서비스가 없으면 items 는 빈 목록으로 둔다.", "hard_rule")
    req = project["requirements"]
    assert req["open_questions"] == []
    assert req["hard_rules"][-1] == {"id": "R4", "text": "서비스가 없으면 items 는 빈 목록으로 둔다.",
                                     "origin": "user", "source_excerpt": "Q1 답"}
    assert req["resolved_questions"][0]["resolved_as"] == "R4"
    assert "비어 있을 때" in req["resolved_questions"][0]["text"]
    assert status(project)["can_confirm"] is True


def test_answer_can_go_to_preferences_or_nowhere() -> None:
    as_pref = questions.resolve(_sample(), "Q1", "짧게 안내", "preference")
    assert as_pref["requirements"]["preferences"][-1]["id"] == "P2"
    as_none = questions.resolve(_sample(), "Q1", "그런 입력은 오지 않는다", "none")
    assert as_none["requirements"]["resolved_questions"][0]["resolved_as"] is None
    assert len(as_none["requirements"]["hard_rules"]) == 3


def test_resolving_changes_requirements_so_a_built_prompt_goes_stale() -> None:
    project = questions.resolve(_sample(), "Q1", "빈 목록", "hard_rule")
    built = builder.build(builder.confirm(project))
    built["requirements"]["open_questions"].append({"id": "Q2", "text": "통화가 둘이면?", "answer": ""})
    built["requirements_revision"] += 1
    reopened = questions.resolve(built, "Q2", "첫 통화만 쓴다", "hard_rule")
    assert status(reopened)["stage"] == "stale_artifact"


@pytest.mark.parametrize("qid, answer, target, message", [
    ("Q1", "  ", "hard_rule", "답을"),
    ("Q9", "답", "hard_rule", "찾을 수"),
    ("Q1", "답", "model", "반영할 곳"),
])
def test_resolve_rejects_bad_requests(qid, answer, target, message) -> None:
    with pytest.raises(ProjectError, match=message):
        questions.resolve(_sample(), qid, answer, target)


def test_projects_saved_before_this_change_still_validate() -> None:
    project = _sample()
    project["requirements"].pop("resolved_questions", None)
    for question in project["requirements"]["open_questions"]:
        question.pop("answer", None)
    validate_project(project)


# --- store --------------------------------------------------------------------


@pytest.fixture
def db(tmp_path) -> Database:
    return Database(tmp_path / "app.db")


@pytest.fixture
def owners(db) -> tuple[int, int]:
    auth = AuthService(db)
    alice, _ = auth.signup("alice", "correct-horse-1")
    bob, _ = auth.signup("bob", "correct-horse-2")
    return alice.id, bob.id


@pytest.fixture
def store(db) -> ProjectStore:
    return ProjectStore(db)


def test_save_appends_versions_and_never_overwrites(store, owners) -> None:
    alice, _ = owners
    project = _sample()
    first = store.save(alice, project, "처음")
    project = questions.resolve(project, "Q1", "빈 목록", "hard_rule")
    second = store.save(alice, project, "Q1 반영")
    assert (first["version"], second["version"]) == (1, 2)
    assert [v["label"] for v in second["versions"]] == ["처음", "Q1 반영"]
    assert store.version(alice, project["id"], 1)["requirements"]["open_questions"][0]["id"] == "Q1"
    assert store.open(alice, project["id"])["project"]["requirements"]["open_questions"] == []


def test_restore_adds_a_copy_as_a_new_version(store, owners) -> None:
    alice, _ = owners
    project = _sample()
    store.save(alice, project)
    store.save(alice, questions.resolve(project, "Q1", "빈 목록", "hard_rule"))
    restored = store.restore(alice, project["id"], 1)
    assert restored["version"] == 3
    assert restored["versions"][-1]["label"] == "v1 복원"
    assert restored["project"]["requirements"]["open_questions"][0]["id"] == "Q1"
    # 복원 전 상태(v2)도 남아 있다.
    assert store.version(alice, project["id"], 2)["requirements"]["open_questions"] == []


def test_list_shows_only_my_projects_latest_first(store, owners) -> None:
    alice, bob = owners
    a, b, c = _sample(), _sample(), _sample()
    a["title"], b["title"], c["title"] = "A", "B", "밥의 것"
    store.save(alice, a)
    store.save(alice, b)
    store.save(bob, c)
    assert [i["title"] for i in store.list(alice)] == ["B", "A"]
    assert [i["title"] for i in store.list(bob)] == ["밥의 것"]


def test_someone_elses_project_looks_like_it_does_not_exist(store, owners) -> None:
    """존재 여부도 알려 주지 않는다 - 내 것이 아니면 없는 것과 같은 오류."""
    alice, bob = owners
    project = _sample()
    store.save(alice, project)
    for call in (lambda: store.open(bob, project["id"]),
                 lambda: store.version(bob, project["id"], 1),
                 lambda: store.restore(bob, project["id"], 1),
                 lambda: store.delete(bob, project["id"])):
        with pytest.raises(KeyError):
            call()
    assert store.open(alice, project["id"])["versions"][0]["version"] == 1


def test_saving_a_project_with_someone_elses_id_creates_a_new_one(store, owners) -> None:
    """다른 사람이 내보낸 project.json 을 가져와 저장해도 그 사람 것에 쓰지 않는다."""
    alice, bob = owners
    project = _sample()
    store.save(alice, project)
    saved = store.save(bob, project, "가져옴")
    assert saved["id"] != project["id"] and saved["version"] == 1
    assert len(store.open(alice, project["id"])["versions"]) == 1


def test_delete_removes_versions_too(store, owners, db) -> None:
    alice, _ = owners
    a, b = _sample(), _sample()
    store.save(alice, a)
    store.save(alice, a)
    store.save(alice, b)
    store.delete(alice, a["id"])
    assert [i["id"] for i in store.list(alice)] == [b["id"]]
    with db.connect() as conn:
        left = conn.execute("SELECT COUNT(*) FROM workspace_versions WHERE project_id = ?", (a["id"],)).fetchone()[0]
    assert left == 0


def test_version_summary_reports_the_last_real_run(store, owners) -> None:
    alice, _ = owners
    project = builder.build(builder.confirm(questions.resolve(_sample(), "Q1", "빈 목록", "hard_rule")))
    project["runs"] = [
        {"status": "ran", "model": "m", "artifact_revision": 1,
         "checks": [{"name": "a", "status": "pass", "detail": "", "group": "contract"},
                    {"name": "b", "status": "not_evaluated", "detail": "", "group": "rules"}]},
        {"status": "preview", "checks": []},
    ]
    summary = store.save(alice, project)["versions"][0]
    assert summary["stage"] == "built"
    assert summary["last_run"]["counts"] == {"pass": 1, "fail": 0, "not_evaluated": 1}


# --- API ----------------------------------------------------------------------


@pytest.fixture
def server(monkeypatch, tmp_path):
    db = Database(tmp_path / "app.db")
    monkeypatch.setattr(api_server, "DB", db)
    monkeypatch.setattr(api_server, "AUTH", AuthService(db))
    monkeypatch.setattr(api_server, "WORKSPACE_STORE", ProjectStore(db))
    srv = ThreadingHTTPServer(("127.0.0.1", 0), api_server.ApiHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/api"
    srv.shutdown()


class Client:
    """쿠키를 들고 다니는 작은 클라이언트 - 브라우저 한 개."""

    def __init__(self, base: str) -> None:
        self.base = base
        self.cookie = ""

    def call(self, path: str, body: dict | None = None) -> tuple[int, dict]:
        data = None if body is None else json.dumps(body).encode()
        headers = {"Content-Type": "application/json"}
        if self.cookie:
            headers["Cookie"] = self.cookie
        req = urllib.request.Request(self.base + path, data, headers)
        try:
            with urllib.request.urlopen(req) as resp:
                self._keep(resp.headers.get("Set-Cookie"))
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as err:
            return err.code, json.loads(err.read())

    def _keep(self, header: str | None) -> None:
        if header:
            pair = header.split(";", 1)[0]
            self.cookie = "" if pair.endswith("=") else pair


def _login(base: str, name: str) -> Client:
    client = Client(base)
    status, _ = client.call("/auth/signup", {"username": name, "password": f"{name}-password-1"})
    assert status == 200
    return client


def test_store_needs_login(server) -> None:
    anonymous = Client(server)
    assert anonymous.call("/workspace/projects")[0] == 401
    _, sample = anonymous.call("/workspace/sample")
    assert anonymous.call("/workspace/projects", {"project": sample["project"]})[0] == 401


def test_reopen_answer_and_restore_over_http(server) -> None:
    alice = _login(server, "alice")
    _, sample = alice.call("/workspace/sample")
    project = sample["project"]
    status_code, saved = alice.call("/workspace/projects", {"project": project, "label": "초안"})
    assert status_code == 200 and saved["version"] == 1

    _, resolved = alice.call("/workspace/resolve",
                             {"project": project, "questionId": "Q1", "answer": "빈 목록", "target": "hard_rule"})
    assert resolved["status"]["can_confirm"] is True
    alice.call("/workspace/projects", {"project": resolved["project"], "label": "Q1 반영"})

    _, listed = alice.call("/workspace/projects")
    assert listed["projects"][0]["versions"] == 2
    _, opened = alice.call(f"/workspace/projects/{project['id']}")
    assert [v["label"] for v in opened["versions"]] == ["초안", "Q1 반영"]
    _, v1 = alice.call(f"/workspace/projects/{project['id']}/versions/1")
    assert v1["project"]["requirements"]["open_questions"]

    _, restored = alice.call(f"/workspace/projects/{project['id']}/restore", {"version": 1})
    assert restored["version"] == 3

    _, gone = alice.call(f"/workspace/projects/{project['id']}/delete", {})
    assert gone == {"deleted": project["id"]}
    assert alice.call(f"/workspace/projects/{project['id']}")[0] == 404


def test_users_cannot_see_each_others_projects_over_http(server) -> None:
    alice, bob = _login(server, "alice"), _login(server, "bob")
    _, sample = alice.call("/workspace/sample")
    alice.call("/workspace/projects", {"project": sample["project"]})
    project_id = sample["project"]["id"]
    assert bob.call("/workspace/projects")[1] == {"projects": []}
    assert bob.call(f"/workspace/projects/{project_id}")[0] == 404
    assert bob.call(f"/workspace/projects/{project_id}/delete", {})[0] == 404
    assert alice.call(f"/workspace/projects/{project_id}")[0] == 200


def test_logout_ends_access(server) -> None:
    alice = _login(server, "alice")
    assert alice.call("/workspace/projects")[0] == 200
    stolen = alice.cookie
    alice.call("/auth/logout", {})
    assert alice.call("/workspace/projects")[0] == 401
    # 로그아웃한 쿠키 값을 다시 보내도 소용없다 (서버에서 세션을 지웠다).
    alice.cookie = stolen
    assert alice.call("/workspace/projects")[0] == 401


def test_store_routes_reject_bad_paths(server) -> None:
    alice = _login(server, "alice")
    assert alice.call("/workspace/projects/0123456789ab")[0] == 404
    assert alice.call("/workspace/projects/0123456789ab/versions/x")[0] == 404
    assert alice.call("/workspace/projectsx")[0] == 404
