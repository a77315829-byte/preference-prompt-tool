"""프로젝트를 다시 열 수 있게 저장한다 (계획서 10절 2차의 영속 저장·버전 이력).

앱 DB(app_db.py, SQLite)의 workspace_projects / workspace_versions 표를 쓴다.
**모든 동작이 소유자(owner_id)를 받는다.** 남의 프로젝트는 있어도 없는 것처럼
다룬다(KeyError) - 다른 사람의 프로젝트 id 가 존재하는지도 알려 주지 않는다.
누가 소유자인지 정하는 것(로그인)은 auth.py 와 api_server.py 의 일이고, 이 모듈은
사용자 정보를 모른다.

- 저장은 **새 버전을 덧붙인다.** 이전 버전을 덮어쓰지 않는다. 복원도 그 버전의
  사본을 새 버전으로 덧붙인다 - 복원 전 상태로 다시 돌아갈 수 있어야 하므로.
- 자동 저장하지 않는다. 사용자가 저장을 누를 때만 쓴다.
- 다른 사람이 내보낸 project.json 을 가져와 저장하면, id 가 겹쳐도 남의 것에
  쓰지 않고 새 id 로 저장한다.
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
MAX_LABEL_CHARS = 60


class StoreError(ValueError):
    """화면에 보여 줄 수 있는 저장 오류 (상한 등)."""


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


class ProjectStore:
    def __init__(self, db: Database) -> None:
        self.db = db

    @staticmethod
    def _owned(conn: sqlite3.Connection, owner_id: int, project_id: str) -> sqlite3.Row:
        row = conn.execute(
            "SELECT id, created_at FROM workspace_projects WHERE id = ? AND owner_id = ?",
            (project_id, owner_id),
        ).fetchone()
        if row is None:
            raise KeyError(project_id)
        return row

    @staticmethod
    def _append(conn: sqlite3.Connection, project_id: str, project: dict[str, Any], label: str) -> int:
        latest = conn.execute(
            "SELECT COALESCE(MAX(version), 0) FROM workspace_versions WHERE project_id = ?", (project_id,)
        ).fetchone()[0]
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

    def _overview(self, conn: sqlite3.Connection, project_id: str) -> dict[str, Any]:
        rows = conn.execute(
            "SELECT version, saved_at, label, project_json FROM workspace_versions WHERE project_id = ? ORDER BY version",
            (project_id,),
        ).fetchall()
        versions = [(r["version"], r["saved_at"], r["label"], json.loads(r["project_json"])) for r in rows]
        return {
            "id": project_id,
            "project": versions[-1][3],
            "versions": [_summary(*v) for v in versions],
        }

    def save(self, owner_id: int, project: dict[str, Any], label: str = "") -> dict[str, Any]:
        """지금 프로젝트를 새 버전으로 덧붙인다. 처음이면 프로젝트를 만든다."""
        validate_project(project)
        project = dict(project)
        with self.db.connect() as conn:
            row = conn.execute("SELECT owner_id FROM workspace_projects WHERE id = ?", (project["id"],)).fetchone()
            if row is not None and row["owner_id"] != owner_id:
                project["id"] = new_id()  # 남의 id 와 겹친다 - 새 프로젝트로 저장
                row = None
            if row is None:
                count = conn.execute(
                    "SELECT COUNT(*) FROM workspace_projects WHERE owner_id = ?", (owner_id,)
                ).fetchone()[0]
                if count >= MAX_PROJECTS_PER_OWNER:
                    raise StoreError(f"프로젝트는 {MAX_PROJECTS_PER_OWNER}개까지 저장할 수 있습니다. 안 쓰는 것을 지워 주세요.")
                now = _now()
                conn.execute(
                    "INSERT INTO workspace_projects (id, owner_id, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                    (project["id"], owner_id, project.get("title") or "", now, now),
                )
            version = self._append(conn, project["id"], project, label)
            return {"version": version, **self._overview(conn, project["id"])}

    def open(self, owner_id: int, project_id: str) -> dict[str, Any]:
        """가장 최근 버전과 버전 목록."""
        with self.db.connect() as conn:
            self._owned(conn, owner_id, project_id)
            return self._overview(conn, project_id)

    def version(self, owner_id: int, project_id: str, version: int) -> dict[str, Any]:
        with self.db.connect() as conn:
            self._owned(conn, owner_id, project_id)
            row = conn.execute(
                "SELECT project_json FROM workspace_versions WHERE project_id = ? AND version = ?",
                (project_id, version),
            ).fetchone()
        if row is None:
            raise KeyError(f"{project_id} v{version}")
        return json.loads(row["project_json"])

    def restore(self, owner_id: int, project_id: str, version: int) -> dict[str, Any]:
        """그 버전의 사본을 새 버전으로 덧붙인다. 아무것도 지우지 않는다."""
        with self.db.connect() as conn:
            self._owned(conn, owner_id, project_id)
            row = conn.execute(
                "SELECT project_json FROM workspace_versions WHERE project_id = ? AND version = ?",
                (project_id, version),
            ).fetchone()
            if row is None:
                raise KeyError(f"{project_id} v{version}")
            new_version = self._append(conn, project_id, json.loads(row["project_json"]), f"v{version} 복원")
            return {"version": new_version, **self._overview(conn, project_id)}

    def delete(self, owner_id: int, project_id: str) -> None:
        with self.db.connect() as conn:
            self._owned(conn, owner_id, project_id)
            conn.execute("DELETE FROM workspace_projects WHERE id = ?", (project_id,))

    def list(self, owner_id: int) -> list[dict[str, Any]]:
        """내 프로젝트 요약, 최근 저장 순."""
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT p.id, p.title, p.updated_at,
                       (SELECT COUNT(*) FROM workspace_versions v WHERE v.project_id = p.id) AS versions,
                       (SELECT project_json FROM workspace_versions v WHERE v.project_id = p.id
                        ORDER BY version DESC LIMIT 1) AS latest
                FROM workspace_projects p WHERE p.owner_id = ? ORDER BY p.updated_at DESC, p.rowid DESC
                """,
                (owner_id,),
            ).fetchall()
        return [
            {
                "id": r["id"],
                "title": r["title"] or "(이름 없음)",
                "saved_at": r["updated_at"],
                "versions": r["versions"],
                "stage": status(json.loads(r["latest"]))["stage"],
            }
            for r in rows
        ]
