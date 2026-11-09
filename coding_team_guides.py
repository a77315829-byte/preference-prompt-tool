"""Explicit coding team defaults and per-task choices; no models or engine changes."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import secrets

from coding_instructions import PREFERENCES, build_coding_instructions
from personal_prompts import PromptConflict, expected_revision
from team import TeamStore, MAX_MEMBERS_PER_TEAM

DOMAIN = "coding_profile"
LABELS = {"explanation": "설명", "comments": "주석", "structure": "구성", "output": "출력"}


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def clean_rules(raw):
    if not isinstance(raw, list) or len(raw) > 12:
        raise ValueError("팀 필수 규칙은 12개까지 입력해 주세요.")
    if any(not isinstance(line, str) or not line.strip() or len(line) > 400 for line in raw):
        raise ValueError("각 규칙은 1~400자로 입력해 주세요.")
    return [line.strip() for line in raw]


def team_profile(raw):
    profile = build_coding_instructions(raw)["profile"]
    # Personal notes and comparison history are never shared through team defaults.
    return {k: profile[k] for k in ("language", "framework", "preferences")}


def render_team_prompt(profile, rules):
    prompt = build_coding_instructions(profile)["prompt"]
    if rules:
        prompt += ("\n\n## 이번 작업의 팀 필수 규칙\n"
                   "아래 규칙은 작성 선호보다 우선한다. 요청과 충돌하면 임의로 생략하지 말고 확인하라.\n"
                   + "\n".join("- " + rule for rule in clean_rules(rules)))
    return prompt


class CodingTeamGuides:
    def __init__(self, db):
        self._db = db

    @property
    def db(self):
        return self._db() if callable(self._db) else self._db

    @staticmethod
    def _read(conn, code, user_id, *, owner=False):
        row = conn.execute("SELECT t.*,g.revision,g.profile_json,g.rules_json FROM teams t "
                           "JOIN coding_team_guides g USING(code) WHERE code=? AND domain_key=?", (code, DOMAIN)).fetchone()
        if row is None:
            raise LookupError("새 코딩 기준 팀을 찾을 수 없습니다. 기존 React 비교 팀과 구분해 주세요.")
        owns = user_id is not None and row["created_by"] == user_id
        member = owns or (user_id is not None and conn.execute(
            "SELECT 1 FROM team_members WHERE code=? AND user_id=?", (code, user_id)).fetchone() is not None)
        if not member or (owner and not owns):
            raise PermissionError("팀 기준은 참여자만 열 수 있고, 변경은 팀장만 할 수 있습니다.")
        return row

    @staticmethod
    def _view(conn, row, user_id):
        members = [r[0] for r in conn.execute("SELECT name FROM team_members WHERE code=? ORDER BY joined_at", (row["code"],))]
        profile, rules = json.loads(row["profile_json"]), json.loads(row["rules_json"])
        return {"code": row["code"], "name": row["name"], "domain_key": DOMAIN,
                "revision": row["revision"], "profile": profile, "rules": rules,
                "members": members, "signedIn": members, "is_member": True, "protected": True,
                "can_manage": row["created_by"] == user_id, "requires_join": False,
                "invite_open": datetime.now(timezone.utc).timestamp() < row["invite_until"],
                "invite_until": row["invite_until"], "prompt": render_team_prompt(profile, rules)}

    def get(self, code, user_id):
        with self.db.connect() as conn:
            return self._view(conn, self._read(conn, code, user_id), user_id)

    def create(self, user, name, raw_profile, raw_rules):
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 60:
            raise ValueError("팀 이름은 1~60자로 입력해 주세요.")
        profile, rules = team_profile(raw_profile), clean_rules(raw_rules)
        code, now = "team-" + secrets.token_urlsafe(12), datetime.now(timezone.utc)
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            TeamStore(self.db)._create_team(conn, code, DOMAIN, user.id, now, name.strip())
            conn.execute("INSERT INTO coding_team_guides(code,profile_json,rules_json) VALUES (?,?,?)",
                         (code, json.dumps(profile, ensure_ascii=False), json.dumps(rules, ensure_ascii=False)))
            conn.execute("INSERT INTO team_members VALUES (?,?,?,?,?,?)", (code, f"user:{user.id}", user.username,
                         user.id, "[]", now.isoformat()))
            return self._view(conn, self._read(conn, code, user.id), user.id)

    def join(self, user, code):
        now = datetime.now(timezone.utc)
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT t.* FROM teams t JOIN coding_team_guides g USING(code) WHERE code=?", (code,)).fetchone()
            if row is None:
                raise LookupError("새 코딩 기준 팀의 초대를 확인해 주세요.")
            known = row["created_by"] == user.id or conn.execute(
                "SELECT 1 FROM team_members WHERE code=? AND user_id=?", (code, user.id)).fetchone()
            if not known:
                if now.timestamp() >= row["invite_until"]:
                    raise PermissionError("초대가 닫혔거나 만료됐습니다. 팀장에게 새 초대를 요청하세요.")
                if conn.execute("SELECT COUNT(*) FROM team_members WHERE code=?", (code,)).fetchone()[0] >= MAX_MEMBERS_PER_TEAM:
                    raise ValueError("팀 참여 인원이 가득 찼습니다.")
                conn.execute("INSERT INTO team_members VALUES (?,?,?,?,?,?)", (code, f"user:{user.id}", user.username,
                             user.id, "[]", now.isoformat()))
            return self._view(conn, self._read(conn, code, user.id), user.id)

    def update(self, user_id, code, revision, profile, rules):
        profile, rules = team_profile(profile), clean_rules(rules)
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = self._read(conn, code, user_id, owner=True)
            if expected_revision(revision) != row["revision"]:
                raise PromptConflict("팀 기준이 바뀌었습니다. 새로 읽은 뒤 변경해 주세요.")
            # Environment is fixed for a team, avoiding silently reinterpreted profiles.
            old = json.loads(row["profile_json"])
            if any(old[k] != profile[k] for k in ("language", "framework")):
                raise ValueError("팀 개발 환경을 바꾸려면 새 팀 기준을 만들어 주세요.")
            conn.execute("UPDATE coding_team_guides SET profile_json=?,rules_json=?,revision=revision+1 WHERE code=?",
                         (json.dumps(profile, ensure_ascii=False), json.dumps(rules, ensure_ascii=False), code))
            return self._view(conn, self._read(conn, code, user_id), user_id)

    def resolve(self, user_id, raw_profile, selection=None):
        draft = build_coding_instructions(raw_profile)
        if not selection:
            return {**draft, "team_context": None, "snapshot": fingerprint(draft)}
        if not isinstance(selection, dict):
            raise ValueError("팀 선택을 확인해 주세요.")
        team = self.get(selection.get("code"), user_id)
        if expected_revision(selection.get("revision")) != team["revision"]:
            raise PromptConflict("팀 기준이 바뀌었습니다. 다시 비교한 뒤 조합해 주세요.")
        profile = draft["profile"]
        if any(profile[k] != team["profile"][k] for k in ("language", "framework")):
            raise ValueError("개인 지침과 팀의 언어·프레임워크가 같아야 합니다.")
        differences = {k for k in PREFERENCES if profile["preferences"][k] != team["profile"]["preferences"][k]}
        choices = selection.get("choices")
        if (not isinstance(choices, dict) or set(choices) != differences
                or any(v not in ("personal", "team") for v in choices.values())):
            raise ValueError("다른 항목마다 개인용 또는 팀용을 골라 주세요.")
        mixed = {**profile, "preferences": {
            k: team["profile"]["preferences"][k] if choices.get(k) == "team" else profile["preferences"][k]
            for k in PREFERENCES}}
        mixed.pop("comparison", None)  # Original A/B evidence does not describe the mixed profile.
        context = {"code": team["code"], "name": team["name"], "revision": team["revision"],
                   "rules": team["rules"], "choices": choices, "source_profile": profile,
                   "team_profile": team["profile"], "method": "explicit_team_defaults"}
        result = {"profile": mixed, "prompt": render_team_prompt(mixed, team["rules"]), "team_context": context}
        return {**result, "snapshot": fingerprint(result)}
