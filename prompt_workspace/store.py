"""프로젝트를 다시 열 수 있게 저장한다 (계획서 10절 2차의 영속 저장·버전 이력).

앱 DB(app_db.py, SQLite)의 workspace_* 표를 쓴다. 누가 로그인했는지 정하는 것은
auth.py 와 api_server.py 의 일이고, 이 모듈은 사용자 id 만 받는다.

**권한은 프로젝트 단위다.**

| 역할 | 열기·비교 | 새 버전 저장·복원·자동 저장 | 공유 관리·삭제 |
|---|---|---|---|
| owner (만든 사람) | O | O | O |
| editor | O | O | X |
| viewer | O | X - 저장하면 자기 사본이 된다 | X |

- 접근 권한이 없는 프로젝트는 있어도 없는 것처럼 다룬다(KeyError). 다른 사람의
  프로젝트 id 가 존재하는지도 알려 주지 않는다.
- 권한은 있지만 그 동작이 안 되면 PermissionError (보기 전용이 복원하려는 경우 등).
- 저장은 **새 버전을 덧붙인다.** 이전 버전을 덮어쓰지 않는다. 복원도 그 버전의
  사본을 새 버전으로 덧붙인다.
- **자동 저장은 버전이 아니다.** 사용자마다 프로젝트마다 작업 중 사본(draft) 하나를
  덮어쓴다. 버전은 사용자가 저장을 누를 때만 생긴다. 편집자 둘이 동시에 고쳐도
  서로의 작업 중 사본을 덮지 않는다.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from app_db import Database
from prompt_workspace.models import new_id, status, validate_project
from prompt_workspace.runner import summarize_checks

MAX_PROJECTS_PER_OWNER = 200
MAX_VERSIONS = 50
MAX_MEMBERS = 20
MAX_LABEL_CHARS = 60
ROLES = ("viewer", "editor")
WRITERS = ("owner", "editor")


class StoreError(ValueError):
    """화면에 보여 줄 수 있는 저장 오류 (상한, 없는 사용자 등)."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _last_ran(project: dict[str, Any]) -> dict[str, Any] | None:
    ran = [r for r in project.get("runs", []) if r.get("status") == "ran"]
    return ran[-1] if ran else None


def _summary(version: int, saved_at: str, label: str, project: dict[str, Any]) -> dict[str, Any]:
    """목록에 보일 한 줄. 스냅샷 전체를 보내지 않는다."""
    run = _last_ran(project)
    return {
        "version": version,
        "saved_at": saved_at,
        "label": label,
        "requirements_revision": project["requirements_revision"],
        "artifact_revision": (project.get("artifact") or {}).get("revision"),
        "stage": status(project)["stage"],
        "last_run": None if run is None else {
            "model": run.get("model"),
            "artifact_revision": run.get("artifact_revision"),
            "counts": summarize_checks(run.get("checks", [])),
        },
    }


def _canonical(project: dict[str, Any]) -> str:
    return json.dumps(project, ensure_ascii=False, sort_keys=True)


class ProjectStore:
    def __init__(self, db: Database) -> None:
        self.db = db

    # --- 권한 ----------------------------------------------------------------

    @staticmethod
    def _role(conn: sqlite3.Connection, user_id: int, project_id: str) -> str:
        """owner / editor / viewer. 접근 권한이 없으면 KeyError (없는 것과 같다)."""
        row = conn.execute(
            """
            SELECT CASE WHEN p.owner_id = ? THEN 'owner' ELSE m.role END AS role
            FROM workspace_projects p
            LEFT JOIN workspace_members m ON m.project_id = p.id AND m.user_id = ?
            WHERE p.id = ?
            """,
            (user_id, user_id, project_id),
        ).fetchone()
        if row is None or row["role"] is None:
            raise KeyError(project_id)
        return row["role"]

    def _require(self, conn: sqlite3.Connection, user_id: int, project_id: str, allowed: tuple[str, ...]) -> str:
        role = self._role(conn, user_id, project_id)
        if role not in allowed:
            raise PermissionError({
                "viewer": "보기 권한만 있는 프로젝트입니다. 저장하면 내 사본으로 저장됩니다.",
                "editor": "이 동작은 프로젝트를 만든 사람만 할 수 있습니다.",
            }.get(role, "권한이 없습니다."))
        return role

    # --- 버전 ----------------------------------------------------------------

    @staticmethod
    def _latest(conn: sqlite3.Connection, project_id: str) -> int:
        return conn.execute(
            "SELECT COALESCE(MAX(version), 0) FROM workspace_versions WHERE project_id = ?", (project_id,)
        ).fetchone()[0]

    def _append(self, conn: sqlite3.Connection, project_id: str, project: dict[str, Any], label: str) -> int:
        latest = self._latest(conn, project_id)
        if latest >= MAX_VERSIONS:
            raise StoreError(f"한 프로젝트의 버전은 {MAX_VERSIONS}개까지입니다. 새 프로젝트로 저장해 주세요.")
        now = _now()
        conn.execute(
            "INSERT INTO workspace_versions (project_id, version, saved_at, label, project_json) VALUES (?, ?, ?, ?, ?)",
            (project_id, latest + 1, now, (label or "").strip()[:MAX_LABEL_CHARS],
             json.dumps(project, ensure_ascii=False)),
        )
        conn.execute(
            "UPDATE workspace_projects SET title = ?, updated_at = ? WHERE id = ?",
            (project.get("title") or "", now, project_id),
        )
        return latest + 1

    def _overview(self, conn: sqlite3.Connection, user_id: int, project_id: str) -> dict[str, Any]:
        role = self._role(conn, user_id, project_id)
        rows = conn.execute(
            "SELECT version, saved_at, label, project_json FROM workspace_versions WHERE project_id = ? ORDER BY version",
            (project_id,),
        ).fetchall()
        versions = [(r["version"], r["saved_at"], r["label"], json.loads(r["project_json"])) for r in rows]
        owner = conn.execute(
            "SELECT u.username FROM workspace_projects p JOIN users u ON u.id = p.owner_id WHERE p.id = ?",
            (project_id,),
        ).fetchone()["username"]
        overview = {
            "id": project_id,
            "role": role,
            "owner": owner,
            "project": versions[-1][3],
            "versions": [_summary(*v) for v in versions],
            "draft": None,
        }
        draft = conn.execute(
            "SELECT saved_at, base_version, project_json FROM workspace_drafts WHERE project_id = ? AND user_id = ?",
            (project_id, user_id),
        ).fetchone()
        if draft is not None:
            draft_project = json.loads(draft["project_json"])
            # 마지막 버전과 내용이 같으면 돌려줄 이유가 없다.
            if _canonical(draft_project) != _canonical(overview["project"]):
                overview["draft"] = {
                    "saved_at": draft["saved_at"],
                    "base_version": draft["base_version"],
                    "project": draft_project,
                }
        if role == "owner":
            overview["members"] = self._members(conn, project_id)
        return overview

    # --- 공개 동작 -----------------------------------------------------------

    def save(self, user_id: int, project: dict[str, Any], label: str = "") -> dict[str, Any]:
        """새 버전으로 덧붙인다. 처음이면 프로젝트를 만든다.

        편집 권한이 없는 프로젝트(보기 전용, 또는 남이 내보낸 파일을 가져온 경우)는
        원본에 쓰지 않고 내 새 프로젝트로 저장한다."""
        validate_project(project)
        project = dict(project)
        with self.db.connect() as conn:
            exists = conn.execute("SELECT 1 FROM workspace_projects WHERE id = ?", (project["id"],)).fetchone()
            role = None
            if exists:
                try:
                    role = self._role(conn, user_id, project["id"])
                except KeyError:
                    role = None
            copied = False
            if exists and role not in WRITERS:
                project["id"] = new_id()
                copied = True
            if not exists or copied:
                count = conn.execute(
                    "SELECT COUNT(*) FROM workspace_projects WHERE owner_id = ?", (user_id,)
                ).fetchone()[0]
                if count >= MAX_PROJECTS_PER_OWNER:
                    raise StoreError(f"프로젝트는 {MAX_PROJECTS_PER_OWNER}개까지 저장할 수 있습니다. 안 쓰는 것을 지워 주세요.")
                now = _now()
                conn.execute(
                    "INSERT INTO workspace_projects (id, owner_id, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                    (project["id"], user_id, project.get("title") or "", now, now),
                )
            version = self._append(conn, project["id"], project, label)
            # 버전으로 저장했으니 내 작업 중 사본은 필요 없다.
            conn.execute("DELETE FROM workspace_drafts WHERE project_id = ? AND user_id = ?", (project["id"], user_id))
            return {"version": version, "copied": copied, **self._overview(conn, user_id, project["id"])}

    def open(self, user_id: int, project_id: str) -> dict[str, Any]:
        """가장 최근 버전, 버전 목록, 내 권한, (있으면) 내 자동 저장본."""
        with self.db.connect() as conn:
            return self._overview(conn, user_id, project_id)

    def version(self, user_id: int, project_id: str, version: int) -> dict[str, Any]:
        with self.db.connect() as conn:
            self._role(conn, user_id, project_id)
            row = conn.execute(
                "SELECT project_json FROM workspace_versions WHERE project_id = ? AND version = ?",
                (project_id, version),
            ).fetchone()
        if row is None:
            raise KeyError(f"{project_id} v{version}")
        return json.loads(row["project_json"])

    def restore(self, user_id: int, project_id: str, version: int) -> dict[str, Any]:
        """그 버전의 사본을 새 버전으로 덧붙인다. 아무것도 지우지 않는다."""
        with self.db.connect() as conn:
            self._require(conn, user_id, project_id, WRITERS)
            row = conn.execute(
                "SELECT project_json FROM workspace_versions WHERE project_id = ? AND version = ?",
                (project_id, version),
            ).fetchone()
            if row is None:
                raise KeyError(f"{project_id} v{version}")
            new_version = self._append(conn, project_id, json.loads(row["project_json"]), f"v{version} 복원")
            conn.execute("DELETE FROM workspace_drafts WHERE project_id = ? AND user_id = ?", (project_id, user_id))
            return {"version": new_version, **self._overview(conn, user_id, project_id)}

    def delete(self, user_id: int, project_id: str) -> None:
        with self.db.connect() as conn:
            self._require(conn, user_id, project_id, ("owner",))
            conn.execute("DELETE FROM workspace_projects WHERE id = ?", (project_id,))

    def list(self, user_id: int) -> list[dict[str, Any]]:
        """내 프로젝트와 나에게 공유된 프로젝트, 최근 저장 순."""
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT p.id, p.title, p.updated_at, u.username AS owner,
                       CASE WHEN p.owner_id = ? THEN 'owner' ELSE m.role END AS role,
                       (SELECT COUNT(*) FROM workspace_versions v WHERE v.project_id = p.id) AS versions,
                       (SELECT project_json FROM workspace_versions v WHERE v.project_id = p.id
                        ORDER BY version DESC LIMIT 1) AS latest,
                       (SELECT saved_at FROM workspace_drafts d WHERE d.project_id = p.id AND d.user_id = ?) AS draft_at
                FROM workspace_projects p
                JOIN users u ON u.id = p.owner_id
                LEFT JOIN workspace_members m ON m.project_id = p.id AND m.user_id = ?
                WHERE p.owner_id = ? OR m.user_id IS NOT NULL
                ORDER BY p.updated_at DESC, p.rowid DESC
                """,
                (user_id, user_id, user_id, user_id),
            ).fetchall()
        return [
            {
                "id": r["id"],
                "title": r["title"] or "(이름 없음)",
                "saved_at": r["updated_at"],
                "versions": r["versions"],
                "stage": status(json.loads(r["latest"]))["stage"],
                "role": r["role"],
                "owner": r["owner"],
                "draft_at": r["draft_at"],
            }
            for r in rows
        ]

    # --- 공유 ----------------------------------------------------------------

    @staticmethod
    def _members(conn: sqlite3.Connection, project_id: str) -> list[dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT u.username, m.role, m.added_at FROM workspace_members m JOIN users u ON u.id = m.user_id
            WHERE m.project_id = ? ORDER BY m.added_at
            """,
            (project_id,),
        ).fetchall()
        return [{"username": r["username"], "role": r["role"], "added_at": r["added_at"]} for r in rows]

    def share(self, user_id: int, project_id: str, username: str, role: str) -> list[dict[str, Any]]:
        """다른 사용자에게 권한을 준다 (이미 있으면 권한만 바꾼다). 소유자만."""
        if role not in ROLES:
            raise StoreError(f"권한은 {ROLES} 중 하나여야 합니다.")
        with self.db.connect() as conn:
            self._require(conn, user_id, project_id, ("owner",))
            target = conn.execute("SELECT id FROM users WHERE username = ?", ((username or "").strip(),)).fetchone()
            if target is None:
                raise StoreError("그 아이디의 사용자를 찾을 수 없습니다.")
            if target["id"] == user_id:
                raise StoreError("내 프로젝트는 이미 모든 권한이 있습니다.")
            existing = conn.execute(
                "SELECT 1 FROM workspace_members WHERE project_id = ? AND user_id = ?", (project_id, target["id"])
            ).fetchone()
            if existing is None:
                count = conn.execute(
                    "SELECT COUNT(*) FROM workspace_members WHERE project_id = ?", (project_id,)
                ).fetchone()[0]
                if count >= MAX_MEMBERS:
                    raise StoreError(f"한 프로젝트는 {MAX_MEMBERS}명까지 공유할 수 있습니다.")
            conn.execute(
                """
                INSERT INTO workspace_members (project_id, user_id, role, added_at) VALUES (?, ?, ?, ?)
                ON CONFLICT (project_id, user_id) DO UPDATE SET role = excluded.role
                """,
                (project_id, target["id"], role, _now()),
            )
            # 보기 전용으로 바뀌면 그 사람의 자동 저장본도 더는 쓸 수 없다.
            if role == "viewer":
                conn.execute("DELETE FROM workspace_drafts WHERE project_id = ? AND user_id = ?",
                             (project_id, target["id"]))
            return self._members(conn, project_id)

    def unshare(self, user_id: int, project_id: str, username: str) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            self._require(conn, user_id, project_id, ("owner",))
            target = conn.execute("SELECT id FROM users WHERE username = ?", ((username or "").strip(),)).fetchone()
            if target is not None:
                conn.execute("DELETE FROM workspace_members WHERE project_id = ? AND user_id = ?",
                             (project_id, target["id"]))
                conn.execute("DELETE FROM workspace_drafts WHERE project_id = ? AND user_id = ?",
                             (project_id, target["id"]))
            return self._members(conn, project_id)

    # --- 자동 저장 -----------------------------------------------------------

    def save_draft(self, user_id: int, project: dict[str, Any]) -> dict[str, Any]:
        """작업 중 사본을 덮어쓴다. 버전을 만들지 않는다. 편집 권한이 있어야 한다."""
        validate_project(project)
        with self.db.connect() as conn:
            self._require(conn, user_id, project["id"], WRITERS)
            now = _now()
            conn.execute(
                """
                INSERT INTO workspace_drafts (project_id, user_id, saved_at, base_version, project_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT (project_id, user_id) DO UPDATE SET
                    saved_at = excluded.saved_at, base_version = excluded.base_version,
                    project_json = excluded.project_json
                """,
                (project["id"], user_id, now, self._latest(conn, project["id"]),
                 json.dumps(project, ensure_ascii=False)),
            )
            return {"saved_at": now}

    def discard_draft(self, user_id: int, project_id: str) -> None:
        with self.db.connect() as conn:
            self._role(conn, user_id, project_id)
            conn.execute("DELETE FROM workspace_drafts WHERE project_id = ? AND user_id = ?", (project_id, user_id))
