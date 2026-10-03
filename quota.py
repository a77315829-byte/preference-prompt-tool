"""하루 사용량 상한 - 사용자별로, 재시작해도 남게 (app_db.py 의 usage 표).

Streamlit 을 import 하지 않는다 (`budget.py` 와 같은 층). React 쪽 API 서버가 쓴다.
Streamlit 앱(app.py)은 계속 budget.DailyBudget(메모리)을 쓴다 - 그 앱은 로그인이 없다.

**두 겹이다.**
1. 서버 전체 상한(total): 결제 쪽 월 상한을 대신하지는 않지만, 하루에 쓸 수 있는 양의
   바닥이다. 예전 DailyBudget 과 같은 역할이고 같은 환경변수를 쓴다.
2. 몫(subject)별 상한: 로그인한 사람은 각자 `per_user`, 로그인하지 않은 방문자는 **모두
   합쳐서** `anon` 하나를 나눠 쓴다. 한 사람이 서버 전체 몫을 다 쓰지 못하게 하려는 것이고,
   익명 방문자가 늘어도 로그인한 사람의 몫은 줄지 않는다.

확인과 차감은 한 트랜잭션(BEGIN IMMEDIATE) 안에서 한다 - 나누면 동시에 온 두 요청이
마지막 한 칸을 같이 가져간다.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Callable, Union

from app_db import Database

ANON = "anon"
# 이보다 오래된 사용량 기록은 지운다. 상한 계산은 오늘 줄만 쓴다 - 나머지는 사후 확인용이다.
KEEP_DAYS = 30


def _utc_today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def subject_for(user_id: int | None) -> str:
    return ANON if user_id is None else f"user:{user_id}"


class Quota:
    def __init__(
        self,
        db: Union[Database, Callable[[], Database]],
        kind: str,
        *,
        total: int,
        per_user: int,
        anon: int | None = None,
        clock: Callable[[], str] = _utc_today,
    ) -> None:
        if min(total, per_user, per_user if anon is None else anon) < 0:
            raise ValueError("상한은 0 이상이어야 한다")
        # Database 또는 그것을 돌려주는 함수. 함수면 쓸 때마다 부른다 - API 서버의 DB 를
        # 테스트가 바꿔 끼워도 상한이 옛 DB(실제 data/app.db)에 쓰지 않게.
        self._db = db
        self.kind = kind
        self.total = total
        self.per_user = per_user
        self.anon = per_user if anon is None else anon
        self._clock = clock

    @property
    def db(self) -> Database:
        return self._db() if callable(self._db) else self._db

    def _limit_for(self, subject: str) -> int:
        return self.anon if subject == ANON else self.per_user

    def try_consume(self, subject: str = ANON) -> str | None:
        """한 번 차감한다. 성공이면 None, 막히면 막힌 이유 - "subject"(내 몫을 다 씀) 또는
        "total"(서버 전체 몫을 다 씀). 막히면 아무것도 바꾸지 않는다."""
        day = self._clock()
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            cutoff = (date.fromisoformat(day) - timedelta(days=KEEP_DAYS)).isoformat()
            conn.execute("DELETE FROM usage WHERE day < ?", (cutoff,))
            used_total = conn.execute(
                "SELECT COALESCE(SUM(count), 0) FROM usage WHERE day = ? AND kind = ?", (day, self.kind)
            ).fetchone()[0]
            used_mine = conn.execute(
                "SELECT COALESCE(count, 0) FROM usage WHERE day = ? AND kind = ? AND subject = ?",
                (day, self.kind, subject),
            ).fetchone()
            used_mine = used_mine[0] if used_mine else 0
            if used_mine >= self._limit_for(subject):
                return "subject"
            if used_total >= self.total:
                return "total"
            conn.execute(
                """
                INSERT INTO usage (day, kind, subject, count) VALUES (?, ?, ?, 1)
                ON CONFLICT (day, kind, subject) DO UPDATE SET count = count + 1
                """,
                (day, self.kind, subject),
            )
            return None

    def consume(self, subject: str = ANON) -> bool:
        return self.try_consume(subject) is None

    def left(self, subject: str = ANON) -> int:
        """오늘 이 몫에서 더 쓸 수 있는 횟수 (서버 전체 몫도 감안)."""
        day = self._clock()
        with self.db.connect() as conn:
            used_total = conn.execute(
                "SELECT COALESCE(SUM(count), 0) FROM usage WHERE day = ? AND kind = ?", (day, self.kind)
            ).fetchone()[0]
            row = conn.execute(
                "SELECT count FROM usage WHERE day = ? AND kind = ? AND subject = ?", (day, self.kind, subject)
            ).fetchone()
        used_mine = row[0] if row else 0
        return max(0, min(self._limit_for(subject) - used_mine, self.total - used_total))

    @property
    def limit(self) -> int:
        """예전 DailyBudget.limit 자리 (서버 시작 안내 문구). 서버 전체 상한."""
        return self.total
