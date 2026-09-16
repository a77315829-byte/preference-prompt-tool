"""하루 사용량 상한(budget.DailyBudget) 검증.

세션당 상한은 브라우저 세션을 새로 열면 우회되므로, 앱 인스턴스가
공유하는 상한이 실제로 막아주는지가 중요하다. app.py 는 이 객체를
st.cache_resource 로 감싸 세션 간에 공유한다.
"""

import threading

import pytest

from budget import DailyBudget


def test_allows_up_to_limit_then_blocks() -> None:
    budget = DailyBudget(3)
    assert budget.left() == 3
    assert [budget.consume() for _ in range(3)] == [True, True, True]
    assert budget.consume() is False
    assert budget.left() == 0
    assert budget.used() == 3


def test_blocked_consume_does_not_change_state() -> None:
    budget = DailyBudget(1)
    assert budget.consume() is True
    for _ in range(5):
        assert budget.consume() is False
    assert budget.used() == 1


def test_zero_limit_blocks_everything() -> None:
    budget = DailyBudget(0)
    assert budget.left() == 0
    assert budget.consume() is False


def test_negative_limit_rejected() -> None:
    with pytest.raises(ValueError):
        DailyBudget(-1)


def test_resets_when_the_day_changes() -> None:
    """날짜가 바뀌면 스스로 초기화돼야 한다. 안 그러면 한 번 소진된 뒤
    앱을 재시작할 때까지 영구히 막힌다."""
    day = {"value": "2026-09-16"}
    budget = DailyBudget(2, clock=lambda: day["value"])

    assert budget.consume() is True
    assert budget.consume() is True
    assert budget.consume() is False

    day["value"] = "2026-09-17"
    assert budget.left() == 2
    assert budget.consume() is True
    assert budget.used() == 1


def test_concurrent_consume_never_exceeds_limit() -> None:
    """확인과 차감이 한 락 안에서 일어나야 한다. 나눠 놓으면 동시에
    들어온 방문자들이 마지막 한 칸을 같이 가져간다."""
    limit = 50
    budget = DailyBudget(limit)
    granted: list[bool] = []
    lock = threading.Lock()
    start = threading.Event()

    def worker() -> None:
        start.wait()
        ok = budget.consume()
        with lock:
            granted.append(ok)

    threads = [threading.Thread(target=worker) for _ in range(limit * 4)]
    for t in threads:
        t.start()
    start.set()
    for t in threads:
        t.join()

    assert sum(granted) == limit
    assert budget.used() == limit
