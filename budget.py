"""앱 인스턴스가 공유하는 하루 사용량 상한.

Streamlit을 import하지 않는다. 그래서 UI 없이 그대로 단위 테스트할 수
있다 (tests/test_budget.py). app.py 가 이 객체를 st.cache_resource 로
감싸서 세션들이 같은 인스턴스를 보게 만든다.

왜 세션당 상한만으로는 부족한가: st.session_state 기반 상한은 브라우저
세션을 새로 열면 그대로 초기화된다. 공개 링크에 불특정 트래픽이 들어오는
상황에서는 그것만으로 팀 API 키를 지킬 수 없다.

이 상한이 대체하지 못하는 것: 앱이 재시작되면 카운터도 0으로 돌아간다.
따라서 결제 쪽 월 지출 상한과 함께 두 겹으로 써야 한다.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone


def _utc_today() -> str:
    """배포 환경은 UTC로 돈다. 로컬 시간대를 쓰면 경계가 환경마다 달라진다."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class DailyBudget:
    """하루에 `limit`번까지만 허용하고, 날짜가 바뀌면 스스로 초기화된다."""

    def __init__(self, limit: int, clock=_utc_today) -> None:
        if limit < 0:
            raise ValueError("limit 은 0 이상이어야 한다")
        self.limit = limit
        self._clock = clock
        self._lock = threading.Lock()
        self._day: str | None = None
        self._used = 0

    def _roll_over_if_needed(self) -> None:
        """호출자가 이미 락을 잡은 상태에서만 부른다."""
        today = self._clock()
        if self._day != today:
            self._day = today
            self._used = 0

    def left(self) -> int:
        """오늘 남은 횟수."""
        with self._lock:
            self._roll_over_if_needed()
            return max(0, self.limit - self._used)

    def consume(self) -> bool:
        """한 번을 차감한다. 남아 있지 않으면 아무것도 바꾸지 않고 False.

        확인과 차감을 한 락 안에서 한다. 나눠 놓으면 두 방문자가 동시에
        마지막 한 칸을 가져갈 수 있다.
        """
        with self._lock:
            self._roll_over_if_needed()
            if self._used >= self.limit:
                return False
            self._used += 1
            return True

    def used(self) -> int:
        with self._lock:
            self._roll_over_if_needed()
            return self._used
