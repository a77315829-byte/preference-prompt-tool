"""계정 간 작업 인수인계. 선호 보관함·팀 투표·모델 실행과 분리한다."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from urllib.parse import urlsplit
import uuid

from auth import USERNAME
from personal_prompts import expected_revision

MAX_HANDOFFS = 100
MAX_VERSIONS = 200
BODY_LIMITS = {"purpose": 3000, "progress": 6000, "remaining": 6000, "prompt": 20000}


class HandoffConflict(ValueError):
    pass


def _text(raw, label, limit, required=True):
    if not isinstance(raw, str) or len(raw) > limit or (required and not raw.strip()):
        raise ValueError(f"{label}은(는) {'1' if required else '0'}~{limit:,}자로 적어 주세요.")
    return raw.strip()


def handoff_fields(raw):
    title = _text(raw.get("title"), "작업 이름", 100)
    labels = {"purpose": "작업 목적", "progress": "진행 상황", "remaining": "남은 일", "prompt": "사용한 프롬프트"}
    body = {k: _text(raw.get(k, ""), labels[k], limit, k != "prompt") for k, limit in BODY_LIMITS.items()}
    references = raw.get("references", [])
    if not isinstance(references, list) or len(references) > 20:
        raise ValueError("참고 파일 경로·링크는 20개까지 저장할 수 있습니다.")
    cleaned = []
    for value in references:
        value = _text(value, "파일 경로·링크", 2048)
        if any(ord(c) < 32 for c in value):
            raise ValueError("참고 자료는 한 줄에 하나씩 적어 주세요.")
        parsed = urlsplit(value)
        if parsed.scheme.lower() in ("http", "https"):
            if not parsed.netloc or not parsed.hostname:
                raise ValueError("참고 링크의 주소를 확인해 주세요.")
        elif parsed.scheme and not (len(parsed.scheme) == 1 and len(value) > 2 and value[1] == ":"):
            raise ValueError("웹 링크는 http 또는 https 주소로 적어 주세요. 파일은 저장소의 경로로 적습니다.")
        if value not in cleaned:
            cleaned.append(value)
    body["references"] = cleaned
    return title, body


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


class HandoffStore:
    def __init__(self, db):
        self._db = db

    @property
    def db(self):
        return self._db() if callable(self._db) else self._db

    @staticmethod
    def _load(conn, user_id, handoff_id):
        row = conn.execute(
            "SELECT h.*, o.username AS owner, r.username AS recipient FROM handoffs h "
            "JOIN users o ON o.id=h.owner_id LEFT JOIN users r ON r.id=h.recipient_id "
            "WHERE h.id=? AND (h.owner_id=? OR h.recipient_id=?)", (handoff_id, user_id, user_id),
        ).fetchone()
        if row is None:
            raise LookupError("인수인계를 찾을 수 없거나 이 계정에 공유되지 않았습니다.")
        return dict(row)

    @staticmethod
    def _public(row, user_id):
        owner = row["owner_id"] == user_id
        recipient = row["recipient_id"] == user_id
        waiting = row["status"] in ("draft", "shared") or row["recipient_id"] is None
        return {**{k: row[k] for k in ("id", "title", "status", "revision", "owner", "recipient", "created_at", "updated_at")},
            "body": json.loads(row["body_json"]), "role": "owner" if owner else "recipient",
            "can_edit": row["status"] != "done" and ((owner and waiting) or (recipient and row["status"] == "active")),
            "can_share": owner and waiting and row["status"] != "done",
            "can_claim": recipient and row["status"] == "shared",
            "can_complete": recipient and row["status"] == "active",
            "can_reopen": recipient and row["status"] == "done"}

    @staticmethod
    def _version(conn, row, user_id, event):
        snapshot = {"title": row["title"], "body": json.loads(row["body_json"]), "status": row["status"], "owner": row["owner"], "recipient": row["recipient"]}
        conn.execute("INSERT INTO handoff_versions VALUES (?,?,?,?,?,?)", (row["id"], row["revision"], user_id, event,
            json.dumps(snapshot, ensure_ascii=False), row["updated_at"]))

    def list_for(self, user_id):
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT h.id FROM handoffs h WHERE owner_id=? OR recipient_id=? ORDER BY updated_at DESC LIMIT 200", (user_id, user_id),
            ).fetchall()
            return [{k: v for k, v in self._public(self._load(conn, user_id, r["id"]), user_id).items() if k != "body"} for r in rows]

    def get(self, user_id, handoff_id):
        with self.db.connect() as conn:
            return self._public(self._load(conn, user_id, handoff_id), user_id)

    def create(self, user_id, raw):
        title, body = handoff_fields(raw)
        handoff_id, now = uuid.uuid4().hex, _now()
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if conn.execute("SELECT COUNT(*) FROM handoffs WHERE owner_id=?", (user_id,)).fetchone()[0] >= MAX_HANDOFFS:
                raise ValueError(f"만든 인수인계는 {MAX_HANDOFFS}개까지 저장할 수 있습니다.")
            conn.execute("INSERT INTO handoffs (id,owner_id,title,body_json,created_at,updated_at) VALUES (?,?,?,?,?,?)",
                (handoff_id, user_id, title, json.dumps(body, ensure_ascii=False), now, now))
            row = self._load(conn, user_id, handoff_id)
            self._version(conn, row, user_id, "created")
            return self._public(row, user_id)

    def change(self, user_id, handoff_id, action, raw):
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = self._load(conn, user_id, handoff_id)
            if row["revision"] != expected_revision(raw.get("revision")):
                raise HandoffConflict("다른 창이나 팀원이 수정했습니다. 입력 내용을 복사해 두고 현재 버전을 다시 열어 주세요.")
            if row["revision"] >= MAX_VERSIONS and action != "complete":
                raise ValueError("이 작업은 저장 버전 상한에 도달했습니다. 현재 내용을 새 인수인계로 정리해 주세요.")
            public = self._public(row, user_id)
            if action == "update":
                if not public["can_edit"]:
                    raise PermissionError("현재 편집 담당자만 수정할 수 있습니다. 받은 작업은 먼저 ‘이어서 맡기’를 누르세요.")
                row["title"], body = handoff_fields(raw)
                row["body_json"] = json.dumps(body, ensure_ascii=False)
            elif action == "share":
                if not public["can_share"]:
                    raise PermissionError("이어서 맡기 전까지 작성자만 받는 팀원을 지정할 수 있습니다.")
                username = raw.get("username")
                if not isinstance(username, str) or not USERNAME.fullmatch(username.strip()):
                    raise ValueError("받을 팀원의 계정 아이디를 적어 주세요.")
                target = conn.execute("SELECT id FROM users WHERE username=?", (username.strip(),)).fetchone()
                if target is None:
                    raise ValueError("그 아이디의 사용자가 없습니다. 같은 서비스에 계정이 있는지 확인해 주세요.")
                if target["id"] == user_id:
                    raise ValueError("작업을 받을 다른 팀원의 아이디를 적어 주세요.")
                if row["recipient_id"] != target["id"]:
                    row["recipient_from_revision"] = row["revision"] + 1
                row.update(recipient_id=target["id"], status="shared")
            elif action in ("claim", "complete", "reopen"):
                capability = {"claim": "can_claim", "complete": "can_complete", "reopen": "can_reopen"}[action]
                if not public[capability]:
                    raise PermissionError("지정된 받는 팀원만 현재 단계에서 이 동작을 할 수 있습니다.")
                row["status"] = {"claim": "active", "complete": "done", "reopen": "active"}[action]
            else:
                raise ValueError("지원하지 않는 인수인계 동작입니다.")
            conn.execute("UPDATE handoffs SET title=?,body_json=?,recipient_id=?,recipient_from_revision=?,status=?,revision=revision+1,updated_at=? WHERE id=?",
                (row["title"], row["body_json"], row["recipient_id"], row["recipient_from_revision"], row["status"], _now(), handoff_id))
            current = self._load(conn, user_id, handoff_id)
            self._version(conn, current, user_id, action)
            return self._public(current, user_id)

    def history(self, user_id, handoff_id, revision=None):
        with self.db.connect() as conn:
            current = self._load(conn, user_id, handoff_id)
            first = 1 if current["owner_id"] == user_id else current["recipient_from_revision"]
            if revision is not None:
                revision = expected_revision(revision)
                if revision < first:
                    raise LookupError("공유 전의 개인 작성 기록은 열 수 없습니다.")
                row = conn.execute("SELECT snapshot_json FROM handoff_versions WHERE handoff_id=? AND revision=?", (handoff_id, revision)).fetchone()
                if row is None:
                    raise LookupError("저장 버전을 찾을 수 없습니다.")
                return {"revision": revision, **json.loads(row["snapshot_json"])}
            rows = conn.execute("SELECT v.revision,v.event,v.saved_at,u.username AS actor FROM handoff_versions v "
                "LEFT JOIN users u ON u.id=v.actor_id WHERE handoff_id=? AND v.revision>=? ORDER BY revision DESC", (handoff_id, first)).fetchall()
            return [dict(r) for r in rows]
