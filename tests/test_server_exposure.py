"""비교 세션의 만료와 보관 개수 상한을 모델 API 호출 없이 검증한다."""

from types import SimpleNamespace

import pytest

import api_server


@pytest.fixture
def empty_sessions(monkeypatch):
    for name in ("SESSIONS", "SESSION_STARTED", "OPTIMIZE_RUNS", "OPTIMIZE_REPORTS"):
        monkeypatch.setattr(api_server, name, {})


def _state(session_id: str, optimize_status: str = "idle"):
    return SimpleNamespace(session_id=session_id, optimize_status=optimize_status)


def test_old_sessions_are_dropped_when_a_new_one_starts(monkeypatch, empty_sessions) -> None:
    monkeypatch.setattr(api_server, "SESSION_TTL_SECONDS", 100)
    api_server._remember_session(_state("old"), now=0)
    api_server.OPTIMIZE_RUNS["old"] = 1
    api_server._remember_session(_state("recent"), now=60)
    api_server._remember_session(_state("new"), now=150)
    assert list(api_server.SESSIONS) == ["recent", "new"]
    assert "old" not in api_server.OPTIMIZE_RUNS


def test_session_count_is_capped_but_a_running_optimization_is_kept(monkeypatch, empty_sessions) -> None:
    monkeypatch.setattr(api_server, "SESSION_TTL_SECONDS", 10_000)
    monkeypatch.setattr(api_server, "MAX_SESSIONS", 2)
    api_server._remember_session(_state("a", optimize_status="running"), now=0)
    api_server._remember_session(_state("b"), now=1)
    api_server._remember_session(_state("c"), now=2)
    # 가장 오래된 a 는 최적화 중이라 남기고, 다음으로 오래된 b 를 지운다.
    assert list(api_server.SESSIONS) == ["a", "c"]
