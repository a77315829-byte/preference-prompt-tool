"""api_server 를 다른 사람이 쓸 수 있게 열었을 때 문제가 되는 두 경로. 네트워크는 쓰지 않는다.

- AWS 실제 조회는 서버 주인의 계정 비용을 읽는다. 브라우저가 보낸 demoMode 하나로 켜지면
  화면을 연 누구나 서버 자격 증명으로 Cost Explorer 를 부를 수 있었다.
- 비교 세션은 메모리에만 있고 데모 세션은 상한 없이 만들 수 있어서, 지우지 않으면 쌓인다.
"""

import sys
from types import SimpleNamespace

import pytest

import api_server
from budget import DailyBudget


class _FakeCostExplorer:
    calls = 0

    def get_cost_and_usage(self, **_):
        _FakeCostExplorer.calls += 1
        return {"ResultsByTime": [{"Groups": [
            {"Keys": ["Amazon EC2"], "Metrics": {"UnblendedCost": {"Amount": "12.5"}}},
        ]}]}


@pytest.fixture
def fake_boto3(monkeypatch):
    _FakeCostExplorer.calls = 0
    monkeypatch.setitem(sys.modules, "boto3", SimpleNamespace(client=lambda *a, **k: _FakeCostExplorer()))
    return _FakeCostExplorer


def _live_request():
    return api_server._aws_cost_report({"demoMode": False, "lookbackDays": 30})


def test_demo_request_never_queries_aws(monkeypatch, fake_boto3) -> None:
    monkeypatch.setattr(api_server, "AWS_LIVE", True)
    report = api_server._aws_cost_report({"demoMode": True})
    assert report["mode"] != "aws" and "liveError" not in report
    assert fake_boto3.calls == 0


def test_live_request_is_ignored_unless_the_server_turns_it_on(monkeypatch, fake_boto3) -> None:
    monkeypatch.setattr(api_server, "AWS_LIVE", False)
    monkeypatch.setattr(api_server, "_subject", lambda: "user:1")
    report = _live_request()
    assert report["mode"] != "aws"
    assert "PPT_AWS_LIVE" in report["liveError"]
    assert fake_boto3.calls == 0


def test_live_request_needs_a_signed_in_user(monkeypatch, fake_boto3) -> None:
    monkeypatch.setattr(api_server, "AWS_LIVE", True)
    monkeypatch.setattr(api_server, "_subject", lambda: api_server.ANON)
    report = _live_request()
    assert report["mode"] != "aws"
    assert "로그인" in report["liveError"]
    assert fake_boto3.calls == 0


def test_live_request_counts_against_a_daily_limit(monkeypatch, fake_boto3) -> None:
    monkeypatch.setattr(api_server, "AWS_LIVE", True)
    monkeypatch.setattr(api_server, "_subject", lambda: "user:1")
    monkeypatch.setattr(api_server, "DAILY_AWS_QUERIES", DailyBudget(1))

    first = _live_request()
    assert first["mode"] == "aws" and first["totalCost"] == "$12.50"
    second = _live_request()
    assert second["mode"] != "aws" and second["liveError"]
    assert fake_boto3.calls == 1


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
