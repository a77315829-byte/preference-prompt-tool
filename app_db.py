"""앱이 쓰는 SQLite 데이터베이스 하나 (사용자 · 세션 · 작업 공간 프로젝트).

Streamlit 을 import 하지 않는다 (`budget.py`, `team.py` 와 같은 층).

**왜 SQLite 인가.** 프로젝트 규칙이 "DB는 SQLite 또는 JSON 파일, 서버형 DB 는
쓰지 않는다"이고, 표준 라이브러리라 의존성이 늘지 않는다. 팀원이 따로 DB 서버를
띄울 필요도 없다. 공개 배포에서 디스크가 재시작마다 지워지는 환경이면 이 파일도
지워진다 - 그때는 이 모듈과 저장소 클래스만 외부 DB 로 바꾼다. 다른 코드는
`Database.connect()` 만 쓴다.

스키마 변경은 `PRAGMA user_version` 으로 순서대로 올린다. 이미 있는 DB 에는 그
뒤의 단계만 적용된다.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

DEFAULT_PATH = Path(__file__).resolve().parent / "data" / "app.db"

# 순서대로 적용한다. 이미 적용된 단계는 고치지 말고 새 단계를 덧붙인다.
MIGRATIONS: list[str] = [
    # 1: 사용자와 세션
    """
    CREATE TABLE users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE COLLATE NOCASE,
        password_hash TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    CREATE TABLE sessions (
        token_hash TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        created_at TEXT NOT NULL,
        expires_at TEXT NOT NULL
    );
    CREATE INDEX sessions_user ON sessions(user_id);
    """,
    # 2: 작업 공간 프로젝트와 버전. 버전은 덧붙이기만 한다 (덮어쓰지 않는다).
    """
    CREATE TABLE workspace_projects (
        id TEXT PRIMARY KEY,
        owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        title TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE INDEX workspace_projects_owner ON workspace_projects(owner_id, updated_at);
    CREATE TABLE workspace_versions (
        project_id TEXT NOT NULL REFERENCES workspace_projects(id) ON DELETE CASCADE,
        version INTEGER NOT NULL,
        saved_at TEXT NOT NULL,
        label TEXT NOT NULL,
        project_json TEXT NOT NULL,
        PRIMARY KEY (project_id, version)
    );
    """,
    # 3: 프로젝트 단위 공유와 자동 저장.
    # - members: 소유자가 다른 사용자에게 준 권한 (viewer 보기 / editor 편집).
    # - drafts: 사용자마다 프로젝트마다 하나. 덮어쓰는 작업 중 사본이고, 버전이 아니다.
    """
    CREATE TABLE workspace_members (
        project_id TEXT NOT NULL REFERENCES workspace_projects(id) ON DELETE CASCADE,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        role TEXT NOT NULL CHECK (role IN ('viewer', 'editor')),
        added_at TEXT NOT NULL,
        PRIMARY KEY (project_id, user_id)
    );
    CREATE INDEX workspace_members_user ON workspace_members(user_id);
    CREATE TABLE workspace_drafts (
        project_id TEXT NOT NULL REFERENCES workspace_projects(id) ON DELETE CASCADE,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        saved_at TEXT NOT NULL,
        base_version INTEGER NOT NULL,
        project_json TEXT NOT NULL,
        PRIMARY KEY (project_id, user_id)
    );
    """,
]


class Database:
    def __init__(self, path: Path | str = DEFAULT_PATH) -> None:
        self.path = Path(path)
        self._migrated = False

    def _open(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def migrate(self) -> None:
        conn = self._open()
        try:
            conn.execute("PRAGMA journal_mode = WAL")
            current = conn.execute("PRAGMA user_version").fetchone()[0]
            for number, script in enumerate(MIGRATIONS[current:], start=current + 1):
                with conn:
                    conn.executescript(f"BEGIN;\n{script}\nPRAGMA user_version = {number};\nCOMMIT;")
        finally:
            conn.close()
        self._migrated = True

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """연결 하나를 열고, 블록이 끝나면 커밋하고 닫는다. 예외면 되돌린다.

        요청마다 새 연결을 연다 - 스레드 서버에서 연결을 공유하지 않으려는 것이고,
        SQLite 연결은 싸다."""
        if not self._migrated:
            self.migrate()
        conn = self._open()
        try:
            with conn:
                yield conn
        finally:
            conn.close()
