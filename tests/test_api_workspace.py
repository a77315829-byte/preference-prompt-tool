"""api_server 의 /api/workspace/* 경로. 실제 API 는 부르지 않는다.

샘플 -> (미결 사항 해결) -> 확인 -> 생성 -> 시험 -> 내보내기를 HTTP 로 완주하고,
비용 상한과 실제 생성 스위치가 지켜지는지 본다."""

from __future__ import annotations

import base64
import io
import json
import threading
import urllib.request
import zipfile
from http.server import ThreadingHTTPServer
from types import SimpleNamespace

import pytest

import api_server
from budget import DailyBudget
from prompt_workspace import llm

GOOD_OUTPUT = json.dumps({
    "currency": "USD", "total": "37.50", "summary": "총 비용은 37.50 USD입니다.",
    "items": [{"service": "Compute", "amount": "25.00"}, {"service": "Storage", "amount": "12.50"}],
})


@pytest.fixture
def server():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), api_server.ApiHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/api"
    srv.shutdown()


@pytest.fixture
def model(monkeypatch, tmp_path):
    calls = []

    def fake(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=GOOD_OUTPUT))], usage=None)

    monkeypatch.setattr(llm, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(llm, "completion", fake)
    monkeypatch.setattr(api_server, "LIVE", True)
    monkeypatch.setattr(api_server, "DAILY_WORKSPACE_CALLS", DailyBudget(5))
    return calls


def _call(base: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(base + path, data, {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read())


def _ready_project(base: str) -> tuple[dict, dict]:
    _, sample = _call(base, "/workspace/sample")
    project = sample["project"]
    project["requirements"]["open_questions"] = []
    project["requirements_revision"] += 1
    _, confirmed = _call(base, "/workspace/confirm", {"project": project})
    _, built = _call(base, "/workspace/build", {"project": confirmed["project"]})
    return built["project"], sample["input"]


def test_full_flow_over_http(server, model) -> None:
    _, sample = _call(server, "/workspace/sample")
    assert sample["status"]["stage"] == "draft" and sample["status"]["can_confirm"] is False
    assert model == []  # 샘플은 AI 를 부르지 않는다

    status, refused = _call(server, "/workspace/confirm", {"project": sample["project"]})
    assert status == 400 and "미결" in refused["error"]

    project, values = _ready_project(server)
    status, ran = _call(server, "/workspace/run", {"project": project, "input": values})
    assert status == 200 and ran["run"]["status"] == "ran" and len(model) == 1

    project["runs"] = [ran["run"]]
    status, exported = _call(server, "/workspace/export", {"project": project, "input": values})
    assert status == 200
    names = zipfile.ZipFile(io.BytesIO(base64.b64decode(exported["zipBase64"]))).namelist()
    assert "prompt-package/render_example.py" in names


def test_input_errors_do_not_spend_the_daily_cap(server, model, monkeypatch) -> None:
    monkeypatch.setattr(api_server, "DAILY_WORKSPACE_CALLS", DailyBudget(1))
    project, values = _ready_project(server)
    for bad in ({**values, "currency": ""}, {**values, "total": "1.00"}, "깨진 입력"):
        status, body = _call(server, "/workspace/run", {"project": project, "input": bad})
        assert status == 200 and body["run"]["status"] in ("input_error", "needs_review")
    assert model == [] and api_server.DAILY_WORKSPACE_CALLS.left() == 1


def test_daily_cap_blocks_model_calls(server, model, monkeypatch) -> None:
    monkeypatch.setattr(api_server, "DAILY_WORKSPACE_CALLS", DailyBudget(0))
    project, values = _ready_project(server)
    status, body = _call(server, "/workspace/run", {"project": project, "input": values})
    assert status == 400 and "모두 썼" in body["error"] and model == []


def test_demo_server_previews_without_calling(server, model, monkeypatch) -> None:
    monkeypatch.setattr(api_server, "LIVE", False)
    project, values = _ready_project(server)
    _, body = _call(server, "/workspace/run", {"project": project, "input": values})
    assert body["run"]["status"] == "preview" and model == []
    status, body = _call(server, "/workspace/structure", {"description": "비용 보고"})
    assert status == 400 and "PPT_LIVE" in body["error"]


def test_bad_project_json_is_a_400_with_a_reason(server, model) -> None:
    status, body = _call(server, "/workspace/build", {"project": {"schema_version": 99}})
    assert status == 400 and "형식" in body["error"]


def test_run_uses_the_server_model_not_the_client(server, model) -> None:
    project, values = _ready_project(server)
    _call(server, "/workspace/run", {"project": project, "input": values, "model": "openai/gpt-expensive"})
    assert model[0]["model"] == api_server.DEFAULT_MODEL
