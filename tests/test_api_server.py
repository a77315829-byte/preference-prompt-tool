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
from agents import prompt_polish as pp


@pytest.fixture()
def server(monkeypatch):
    monkeypatch.setattr(api_server, "SESSIONS", {})
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
