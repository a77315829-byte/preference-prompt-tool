"""계정별 개인 프롬프트 보관함. 비교·팀·업무 작업 공간과 분리한다."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import uuid

SUPPORTED_DOMAINS = frozenset({"coding", "summarization", "summarization_ko"})
MAX_PROMPTS = 100
MAX_PROMPT_CHARS = 20_000


class PromptConflict(ValueError):
    pass


def _text(value, label: str, limit: int, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > limit or (required and not value.strip()):
        raise ValueError(f"{label}은(는) {'1' if required else '0'}~{limit:,}자로 적어 주세요.")
    return value.strip()


def _fields(body: dict) -> tuple[str, str, str, str]:
    title = _text(body.get("title"), "이름", 100)
    domain = body.get("domainKey")
    if not isinstance(domain, str) or domain not in SUPPORTED_DOMAINS:
        raise ValueError("문서 요약(한국어·영어) 또는 코딩용 프롬프트를 선택해 주세요.")
    return title, domain, _text(body.get("prompt"), "프롬프트", MAX_PROMPT_CHARS), _text(body.get("note", ""), "설명", 1000, False)


def expected_revision(value) -> int:
    if type(value) is not int or value < 1:
        raise ValueError("저장된 버전을 다시 확인해 주세요.")
    return value


class PersonalPromptStore:
    def __init__(self, db):
        self._db = db

    @property
    def db(self):
        return self._db() if callable(self._db) else self._db

    def list_for(self, owner_id: int) -> list[dict]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT id, title, domain_key, note, revision, created_at, updated_at, provenance_json FROM personal_prompts "
                "WHERE owner_id = ? ORDER BY updated_at DESC, rowid DESC", (owner_id,),
            ).fetchall()
            result = []
            for row in rows:
                item = dict(row)
                raw = item.pop("provenance_json")
                origin = json.loads(raw) if raw else {}
                parent = origin.get("remixed_from")
                kind = origin.get("operation") or ("derived" if parent else "task" if origin else "personal")
                item["lineage"] = {"kind": kind, "parent": {k: parent[k] for k in ("id", "title", "revision") if k in parent} if parent else None}
                result.append(item)
            return result

    def get(self, owner_id: int, prompt_id: str) -> dict:
        with self.db.connect() as conn:
            return self._get(conn, owner_id, prompt_id)

    @staticmethod
    def _get(conn, owner_id: int, prompt_id: str) -> dict:
        row = conn.execute(
            "SELECT id, title, domain_key, prompt, note, revision, created_at, updated_at, provenance_json FROM personal_prompts "
            "WHERE id = ? AND owner_id = ?", (prompt_id, owner_id),
        ).fetchone()
        if row is None:
            raise LookupError("보관한 프롬프트를 찾을 수 없습니다.")
        item = dict(row)
        raw = item.pop("provenance_json")
        provenance = json.loads(raw) if raw else None
        item["provenance"] = provenance
        item["provenance_matches"] = (provenance["domain_key"] == item["domain_key"] and
                                      provenance["prompt_sha256"] == hashlib.sha256(item["prompt"].encode()).hexdigest()) if provenance else None
        return item

    def create(self, owner_id: int, body: dict, *, provenance: dict | None = None) -> dict:
        title, domain, prompt, note = _fields(body)
        prompt_id = uuid.uuid4().hex
        now = datetime.now(timezone.utc).isoformat(timespec="microseconds")
        # 출처는 검증된 서버 호출만 전달한다. 일반 CRUD 요청 body의 메타데이터는 무시한다.
        provenance_json = json.dumps({**provenance, "domain_key": domain, "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest()},
                                     ensure_ascii=False) if provenance is not None else None
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if conn.execute("SELECT COUNT(*) FROM personal_prompts WHERE owner_id = ?", (owner_id,)).fetchone()[0] >= MAX_PROMPTS:
                raise ValueError(f"보관함에는 {MAX_PROMPTS}개까지 저장할 수 있습니다. 쓰지 않는 항목을 정리해 주세요.")
            conn.execute(
                "INSERT INTO personal_prompts (id, owner_id, title, domain_key, prompt, note, created_at, updated_at, provenance_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (prompt_id, owner_id, title, domain, prompt, note, now, now, provenance_json),
            )
            return self._get(conn, owner_id, prompt_id)

    def update(self, owner_id: int, prompt_id: str, body: dict) -> dict:
        title, domain, prompt, note = _fields(body)
        revision = expected_revision(body.get("revision"))
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            current = self._get(conn, owner_id, prompt_id)
            if current["revision"] != revision:
                raise PromptConflict("다른 창에서 수정된 항목입니다. 내 수정 내용을 복사해 두고 다시 열어 주세요.")
            conn.execute(
                "UPDATE personal_prompts SET title = ?, domain_key = ?, prompt = ?, note = ?, "
                "revision = revision + 1, updated_at = ? WHERE id = ? AND owner_id = ?",
                (title, domain, prompt, note, datetime.now(timezone.utc).isoformat(timespec="microseconds"), prompt_id, owner_id),
            )
            return self._get(conn, owner_id, prompt_id)

    def delete(self, owner_id: int, prompt_id: str, revision) -> None:
        revision = expected_revision(revision)
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            current = self._get(conn, owner_id, prompt_id)
            if current["revision"] != revision:
                raise PromptConflict("다른 창에서 수정된 항목입니다. 다시 열어 확인한 뒤 삭제해 주세요.")
            conn.execute("DELETE FROM personal_prompts WHERE id = ? AND owner_id = ?", (prompt_id, owner_id))
