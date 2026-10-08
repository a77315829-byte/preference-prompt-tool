"""api_server.py 의 /api/polish, /api/polish/checklist, AWS sourceText 회귀 테스트.

실제 서버를 임시 포트에 띄우고 stdlib http.client 로만 호출한다 - 새
의존성을 추가하지 않는다(절대 규칙 3). 세션류 엔드포인트는 이미
프론트가 codingApi.js 로 실사용 검증 중이라 여기서는 이번에 추가한
polish 경로와 AWS sourceText 구성만 다룬다.
"""

from __future__ import annotations

import json
import threading
from http.client import HTTPConnection

import pytest

import api_server
from budget import DailyBudget
from agents import prompt_polish as pp


@pytest.fixture()
def server(monkeypatch):
    monkeypatch.setattr(api_server, "SESSIONS", {})
    # AI 다듬기는 실제 생성 모드에서만, 하루 상한 안에서만 돈다.
    monkeypatch.setattr(api_server, "LIVE", True)
    monkeypatch.setattr(api_server, "DAILY_POLISHES", DailyBudget(100))
    httpd = api_server.ThreadingHTTPServer(("127.0.0.1", 0), api_server.ApiHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield httpd.server_address
    finally:
        httpd.shutdown()
        thread.join(timeout=2)


def _post(address, path: str, payload: dict) -> tuple[int, dict]:
    conn = HTTPConnection(*address, timeout=5)
    body = json.dumps(payload).encode("utf-8")
    conn.request("POST", path, body=body, headers={"Content-Type": "application/json"})
    resp = conn.getresponse()
    data = json.loads(resp.read().decode("utf-8") or "{}")
    conn.close()
    return resp.status, data


# ── /api/polish/checklist: 모델 호출 없이 코드만 돈다 ─────────────────

def test_checklist_endpoint_needs_no_model_call(server, monkeypatch) -> None:
    def fail_if_called(**kwargs):
        raise AssertionError("checklist 경로는 모델을 부르면 안 된다")

    monkeypatch.setattr(pp, "completion", fail_if_called)

    status, data = _post(server, "/api/polish/checklist", {"prompt": "요약해줘"})

    assert status == 200
    names = {item["name"] for item in data["checklist"]}
    assert "역할 지정" in names
    assert "suggestions" not in data


def test_checklist_endpoint_rejects_empty_prompt(server) -> None:
    status, data = _post(server, "/api/polish/checklist", {"prompt": "   "})
    assert status == 400
    assert "error" in data


def test_checklist_endpoint_rejects_oversized_prompt(server) -> None:
    status, _data = _post(
        server, "/api/polish/checklist",
        {"prompt": "x" * (api_server.MAX_POLISH_PROMPT_CHARS + 1)},
    )
    assert status == 400


# ── /api/polish: 체크리스트 + LLM 재작성 ───────────────────────────────

class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = type("M", (), {"content": content})()


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.choices = [_FakeChoice(content)]


FAKE_REPLY = "역할이 없다.\n---다듬은 프롬프트---\n[역할]\n[ ]\n[목표]\n요약"


def test_polish_endpoint_returns_checklist_and_rewrite(server, monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(pp, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(pp, "completion", lambda **kw: _FakeResponse(FAKE_REPLY))

    status, data = _post(server, "/api/polish", {"prompt": "요약해줘", "model": "fake/model"})

    assert status == 200
    assert data["suggestions"] == "역할이 없다."
    assert data["revisedPrompt"].startswith("[역할]")
    assert any(item["name"] == "역할 지정" for item in data["checklist"])


def test_polish_endpoint_ignores_client_chosen_model(server, monkeypatch, tmp_path) -> None:
    """모델은 서버가 정한다. 요청 본문을 따르면 누구든 비싼 모델 이름을
    보내 서버 키로 호출할 수 있다."""
    monkeypatch.setattr(pp, "CACHE_DIR", tmp_path)
    seen = {}

    def fake_completion(**kwargs):
        seen["model"] = kwargs["model"]
        return _FakeResponse(FAKE_REPLY)

    monkeypatch.setattr(pp, "completion", fake_completion)
    _post(server, "/api/polish", {"prompt": "요약해줘", "model": "openai/some-expensive-model"})
    assert seen["model"] == api_server.DEFAULT_MODEL


def _forbid_model_call(**kwargs):
    raise AssertionError("모델을 부르면 안 된다")


def test_polish_needs_live_mode(server, monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(pp, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(pp, "completion", _forbid_model_call)
    monkeypatch.setattr(api_server, "LIVE", False)
    status, data = _post(server, "/api/polish", {"prompt": "요약해줘"})
    assert status == 400 and "PPT_LIVE" in data["error"]


def test_polish_daily_cap(server, monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(pp, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(pp, "completion", _forbid_model_call)
    monkeypatch.setattr(api_server, "DAILY_POLISHES", DailyBudget(0))
    status, data = _post(server, "/api/polish", {"prompt": "요약해줘"})
    assert status == 400 and "횟수" in data["error"]


def test_polish_reply_without_separator_is_not_cached(server, monkeypatch, tmp_path) -> None:
    """구분선이 없는 응답을 캐시에 굳히면 다시 시도해도 계속 빈 결과가 나온다."""
    monkeypatch.setattr(pp, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(pp, "completion", lambda **kw: _FakeResponse("설명만 있고 구분선이 없다"))
    status, _ = _post(server, "/api/polish", {"prompt": "요약해줘"})
    assert status == 400
    assert not list(tmp_path.glob("*.json"))


def test_polish_cache_key_follows_the_instructions(monkeypatch, tmp_path) -> None:
    """지시문을 고치면 캐시가 무효화돼야 한다."""
    monkeypatch.setattr(pp, "CACHE_DIR", tmp_path)
    calls = []
    monkeypatch.setattr(pp, "completion", lambda **kw: calls.append(kw) or _FakeResponse(FAKE_REPLY))
    pp.polish("요약해줘", model="m")
    pp.polish("요약해줘", model="m")
    assert len(calls) == 1
    monkeypatch.setattr(pp, "_REFLECTION_INSTRUCTIONS", pp._REFLECTION_INSTRUCTIONS + "\n")
    pp.polish("요약해줘", model="m")
    assert len(calls) == 2
    assert calls[0]["timeout"] == pp.REQUEST_TIMEOUT_SECONDS
    assert calls[0]["max_tokens"] == pp.MAX_OUTPUT_TOKENS


def test_polish_endpoint_uses_default_model_when_none_given(server, monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(pp, "CACHE_DIR", tmp_path)
    seen = {}

    def fake_completion(**kwargs):
        seen["model"] = kwargs["model"]
        return _FakeResponse(FAKE_REPLY)

    monkeypatch.setattr(pp, "completion", fake_completion)

    _post(server, "/api/polish", {"prompt": "요약해줘"})

    assert seen["model"] == api_server.DEFAULT_MODEL


# ── AWS 비용 리포트의 sourceText: 생성기가 실제 숫자를 받는지 ─────────
#
# 예전엔 sourceText가 "찾았으니 확인하세요" 한 줄이라, 화면(카드)엔 진짜
# 금액·리소스ID가 있는데 그걸 요약하는 생성기는 받지 못했다 - 출력의
# 구체적인 숫자는 전부 모델이 지어낸 것일 수밖에 없었다.

def test_demo_report_source_text_carries_the_real_numbers() -> None:
    report = api_server._demo_aws_cost_report()
    assert report["totalCost"] in report["sourceText"]
    for finding in report["findings"]:
        assert finding["cost"] in report["sourceText"]
        assert finding["resourceId"] in report["sourceText"]


def test_report_source_text_helper_handles_missing_fields_without_crashing() -> None:
    # boto3 조회 결과가 일부 필드를 안 채울 수도 있다 - KeyError로 죽으면
    # 화면 전체가 죽는다.
    minimal = {"totalCost": "$1.00", "findings": [{"service": "EC2"}]}
    text = api_server._report_source_text(minimal)
    assert "$1.00" in text
    assert "EC2" in text
