"""팀 모드: 여러 사람의 선택을 합쳐 팀 공통 프롬프트를 만든다.

Streamlit 을 import 하지 않는다 (`service.py`, `exporters.py` 와 같은 층).

타깃을 "AI 를 매일 쓰는 작은 개발팀"으로 잡은 근거가 되는 기능이다. 예를 들어
팀원 셋이 각자 코딩 비교를 하면, 세 사람의 비교를 모두 한 추정기에 넣어 팀
선호를 정하고, 사람마다 갈린 축은 "합의가 필요한 항목"으로 보여 준다.

**저장하는 것:** 팀 코드, 이름, 선택 기록(어느 두 조합 중 무엇을 골랐는지).
원문과 생성 결과는 저장하지 않는다. 앱 DB(app_db.py, SQLite)에 남아 서버를 다시
켜도 사라지지 않는다. 대신 30일 동안 아무도 참여하지 않은 팀은 지운다 (아래 상한 참고).

**누가 누구로 참여하나.** 로그인한 사람은 자기 아이디로만 참여한다(이름을 고를 수
없다). 로그인하지 않은 사람은 이름을 적는다 - 다만 로그인한 팀원의 아이디와 같은 이름은
쓸 수 없다. 그 사람을 사칭하거나 그 기록을 덮어쓰지 못하게. 같은 이름의 익명 참여자끼리는
예전처럼 나중 것이 앞의 것을 바꾼다(다시 해 본 경우).

이 모듈은 도메인을 모른다. 축 이름과 값은 도메인 정의에서 읽는다.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable

from engine.domain_loader import Domain
from engine.estimator import Comparison, Estimator

MAX_MEMBERS_PER_TEAM = 20
MAX_TEAMS = 200
# 팀이 DB 에 남으므로 전체 상한이 영구적이다. 두 가지로 막힌 상태가 굳지 않게 한다.
# - 로그인하지 않은 방문자가 만든 팀은 모두 합쳐 MAX_ANON_TEAMS 개까지 (데모 세션 하나로
#   아무 코드나 만들 수 있어서, 이게 없으면 익명 방문자가 전체 상한을 다 채운다).
#   로그인한 사람은 각자 MAX_TEAMS_PER_USER 개까지.
# - TEAM_IDLE_DAYS 동안 아무도 참여하지 않은 팀은 새 팀을 만들 때 지운다.
MAX_ANON_TEAMS = 50
MAX_TEAMS_PER_USER = 20
TEAM_IDLE_DAYS = 30
_CODE = re.compile(r"^[A-Za-z0-9_-]{3,32}$")
MAX_NAME_CHARS = 20

History = list[tuple[dict[str, str], dict[str, str], str]]


class TeamError(ValueError):
    pass


@dataclass
class Member:
    name: str
    history: History
    # 로그인한 계정으로 참여했는가. 화면이 이름 옆에 표시한다.
    signed_in: bool = False


class TeamStore:
    """팀 코드 -> 팀. DB 에 둔다."""

    def __init__(self, db, clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> None:
        # Database 또는 그것을 돌려주는 함수 (quota.Quota 와 같은 이유).
        self._db = db
        self._clock = clock

    @property
    def db(self):
        return self._db() if callable(self._db) else self._db

    def add(self, code: str, domain_key: str, name: str, history: History,
            user_id: int | None = None, username: str | None = None) -> list[Member]:
        """팀에 더한다. 같은 사람(로그인한 사람은 같은 아이디, 아니면 같은 이름)이 다시
        더하면 그 사람의 기록을 새것으로 바꾼다 (다시 해 본 경우)."""
        if not _CODE.match(code or ""):
            raise TeamError("팀 코드는 영문·숫자·-·_ 3~32자여야 합니다.")
        if user_id is not None:
            name, key = username or "", f"user:{user_id}"
        else:
            name = (name or "").strip()
            if not name or len(name) > MAX_NAME_CHARS:
                raise TeamError(f"이름은 1~{MAX_NAME_CHARS}자여야 합니다.")
            key = f"name:{name.lower()}"
        if not history:
            raise TeamError("선택 기록이 없는 세션은 팀에 더할 수 없습니다.")
        now_dt = self._clock()
        now = now_dt.isoformat(timespec="seconds")
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            team = conn.execute("SELECT domain_key FROM teams WHERE code = ?", (code,)).fetchone()
            if team is None:
                self._expire_idle(conn, now_dt)
                if user_id is None:
                    made = conn.execute("SELECT COUNT(*) FROM teams WHERE created_by IS NULL").fetchone()[0]
                    if made >= MAX_ANON_TEAMS:
                        raise TeamError("로그인하지 않은 방문자가 만들 수 있는 팀이 다 찼습니다. "
                                        "로그인하면 새 팀을 만들 수 있고, 이미 있는 팀 코드에는 그대로 참여할 수 있습니다.")
                elif conn.execute("SELECT COUNT(*) FROM teams WHERE created_by = ?",
                                  (user_id,)).fetchone()[0] >= MAX_TEAMS_PER_USER:
                    raise TeamError(f"한 사람이 만들 수 있는 팀은 {MAX_TEAMS_PER_USER}개까지입니다.")
                if conn.execute("SELECT COUNT(*) FROM teams").fetchone()[0] >= MAX_TEAMS:
                    raise TeamError("지금은 새 팀을 만들 수 없습니다. 잠시 뒤 다시 시도해 주세요.")
                conn.execute("INSERT INTO teams (code, domain_key, created_by, created_at) VALUES (?, ?, ?, ?)",
                             (code, domain_key, user_id, now))
            elif team["domain_key"] != domain_key:
                raise TeamError(f"이 팀 코드는 다른 카테고리({team['domain_key']})에 쓰이고 있습니다.")
            if user_id is None:
                # 익명 이름이 로그인한 팀원의 아이디와 같으면 거부 (사칭 방지).
                taken = conn.execute(
                    "SELECT 1 FROM team_members WHERE code = ? AND user_id IS NOT NULL AND lower(name) = ?",
                    (code, name.lower()),
                ).fetchone()
                if taken:
                    raise TeamError(f"'{name}' 은 이 팀에서 로그인한 팀원의 아이디입니다. 다른 이름을 쓰거나 로그인해 주세요.")
            exists = conn.execute("SELECT 1 FROM team_members WHERE code = ? AND member_key = ?",
                                  (code, key)).fetchone()
            if not exists and conn.execute("SELECT COUNT(*) FROM team_members WHERE code = ?",
                                           (code,)).fetchone()[0] >= MAX_MEMBERS_PER_TEAM:
                raise TeamError(f"한 팀은 {MAX_MEMBERS_PER_TEAM}명까지입니다.")
            conn.execute(
                """
                INSERT INTO team_members (code, member_key, name, user_id, history_json, joined_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT (code, member_key) DO UPDATE SET
                    name = excluded.name, history_json = excluded.history_json, joined_at = excluded.joined_at
                """,
                (code, key, name, user_id, json.dumps([list(c) for c in history], ensure_ascii=False), now),
            )
            return self._members(conn, code)

    @staticmethod
    def _expire_idle(conn, now: datetime) -> None:
        """TEAM_IDLE_DAYS 동안 아무도 참여하지 않은 팀을 지운다 (팀원은 CASCADE)."""
        cutoff = (now - timedelta(days=TEAM_IDLE_DAYS)).isoformat(timespec="seconds")
        conn.execute(
            """
            DELETE FROM teams WHERE COALESCE(
                (SELECT MAX(joined_at) FROM team_members m WHERE m.code = teams.code), teams.created_at
            ) < ?
            """,
            (cutoff,),
        )

    @staticmethod
    def _members(conn, code: str) -> list[Member]:
        rows = conn.execute(
            "SELECT name, user_id, history_json FROM team_members WHERE code = ? ORDER BY joined_at, rowid", (code,)
        ).fetchall()
        return [Member(r["name"], [tuple(c) for c in json.loads(r["history_json"])], signed_in=r["user_id"] is not None)
                for r in rows]

    def get(self, code: str) -> tuple[str, list[Member]]:
        with self.db.connect() as conn:
            team = conn.execute("SELECT domain_key FROM teams WHERE code = ?", (code,)).fetchone()
            if team is None:
                raise TeamError("아직 아무도 참여하지 않은 팀 코드입니다.")
            return team["domain_key"], self._members(conn, code)


def _estimator(domain: Domain, histories: list[History]) -> Estimator:
    estimator = Estimator(domain)
    for history in histories:
        for combo_a, combo_b, winner in history:
            estimator.update(Comparison(combo_a=combo_a, combo_b=combo_b, winner=winner))
    return estimator


@dataclass(frozen=True)
class AxisAgreement:
    axis: str
    team_value: str
    votes: dict[str, int]  # 값 -> 그 값을 1위로 고른 사람 수
    agreed: bool
    # 최다 득표가 둘 이상이면 팀 프롬프트의 값은 비교를 합친 결과일 뿐
    # 다수결이 아니다. 화면에서 "팀이 정해야 한다"고 알린다.
    tied: bool = False
    # 아무도 이 축에서 선호를 정하지 않았다 ("비슷하다"만 골랐거나 묻지 않았다).
    # 팀 프롬프트에서 빠지고, team_value 는 빈 문자열이다.
    undecided: bool = False


def _equal_weight_team(domain: Domain, personal: list[Estimator]) -> Estimator:
    """팀원마다 한 표. 축마다 각자의 1위 값으로 다수결하고, 동률이면 사람마다 같은
    무게로 평균한 값별 확률(softmax)이 큰 쪽을 고른다.

    예전에는 모든 비교를 한 추정기에 넣어서, 같은 쪽을 여러 번 고른 한 사람이 다른 두
    사람을 이길 수 있었다. 확률을 평균하는 것만으로는 부족했다 - 같은 쪽을 12번 고른
    사람은 0.99 로 확신하고 1번 고른 사람은 0.62 라, 여전히 한 사람이 둘을 이긴다.
    돌려주는 추정기의 효용은 (표 수 + 평균 확률) 이라 1위가 다수결 결과가 된다
    (평균 확률은 1 보다 작으므로 표 수가 같을 때만 순서를 가른다).

    그 축에서 선호를 정하지 않은 사람(효용이 모두 같다)은 표를 던지지 않는다. 안 그러면
    정의상 첫 값에 표가 가서, 고르지 않은 선택이 다수결을 바꾼다. 아무도 정하지 않은
    축은 효용이 모두 0 으로 남아 has_signal 이 False 가 된다."""
    team_estimator = Estimator(domain)
    for axis in team_estimator.enum_axis_names():
        voters = [e for e in personal if e.has_signal(axis)]
        if not voters:
            continue
        values = list(team_estimator.utilities[axis])
        votes = dict.fromkeys(values, 0)
        mean = dict.fromkeys(values, 0.0)
        for estimator in voters:
            votes[estimator.preferred_value(axis)] += 1
            utilities = estimator.utilities[axis]
            top = max(utilities.values())
            exps = {v: math.exp(utilities[v] - top) for v in values}
            total = sum(exps.values())
            for v in values:
                mean[v] += exps[v] / total / len(voters)
        team_estimator.utilities[axis] = {v: votes[v] + mean[v] for v in values}
    return team_estimator


def summarize(domain: Domain, members: list[Member]) -> tuple[Estimator, list[AxisAgreement]]:
    """팀 추정과, 축마다 사람들이 어떻게 갈렸는지. 사람별 1위는 각자의 기록만으로
    따로 추정하고, 팀 추정은 그 사람들을 같은 무게로 합친다 (비교 횟수와 무관하게)."""
    personal = [_estimator(domain, [m.history]) for m in members]
    team_estimator = _equal_weight_team(domain, personal)
    agreements = []
    for axis in team_estimator.enum_axis_names():
        # 선호를 정한 사람만 센다 (_equal_weight_team 과 같은 기준).
        votes = Counter(e.preferred_value(axis) for e in personal if e.has_signal(axis))
        # 두 경우를 가른다: 아무도 선호를 정하지 않음(표가 없다)과, 의견이 정확히 반으로
        # 갈림(표는 있는데 합친 효용이 같다 - 1:1 이고 두 사람의 확신이 대칭이면 그렇다).
        # 둘 다 팀 프롬프트에서는 빠지지만 화면에 보일 말이 다르다.
        undecided = not votes
        decided = team_estimator.has_signal(axis)
        agreements.append(AxisAgreement(
            axis=axis,
            team_value=team_estimator.preferred_value(axis) if decided else "",
            votes=dict(votes.most_common()),
            agreed=len(votes) == 1,
            tied=len(votes) > 1 and sum(1 for n in votes.values() if n == max(votes.values())) > 1,
            undecided=undecided,
        ))
    return team_estimator, agreements
