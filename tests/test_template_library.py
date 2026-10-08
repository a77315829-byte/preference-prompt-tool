"""템플릿 라이브러리 검증. API 호출은 없다."""

import json

import pytest
import yaml

import service
import template_library
from engine.domain_loader import load_domain
from engine.generator import build_final_prompt, build_preference_section, build_template_prompt

SOURCE = "The council approved a housing plan. It adds homes. Critics worry about prices."


def test_shipped_library_loads_and_covers_the_core_categories() -> None:
    templates = template_library.load_library()
    assert len({t.id for t in templates}) == len(templates)
    assert {t.domain for t in templates} >= {"summarization", "summarization_ko", "coding", "idle_tracker"}
    for t in templates:
        load_domain(f"domains/{t.domain}.yaml")  # 도메인이 실제로 로드돼야 한다


@pytest.mark.parametrize(
    "broken, message",
    [
        ({"domain": "no_such_domain"}, "도메인"),
        ({"prompt": ""}, "prompt"),
        ({"license": None}, "license"),
    ],
)
def test_malformed_template_is_rejected(tmp_path, broken, message) -> None:
    raw = yaml.safe_load(template_library.LIBRARY_PATH.read_text(encoding="utf-8"))
    raw["templates"][0].update(broken)
    path = tmp_path / "library.yaml"
    path.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
    with pytest.raises(template_library.TemplateError, match=message):
        template_library.load_library(path)


def test_template_prompt_is_template_plus_preferences() -> None:
    domain = load_domain("domains/summarization.yaml")
    combo = {"length": "short", "extractiveness": "high", "topic": ""}
    prompt = build_template_prompt(domain, combo, "TEMPLATE BODY\n")
    section = build_preference_section(domain, combo)
    assert prompt == f"TEMPLATE BODY\n\n{section}"
    # 최종 프롬프트의 선호 절과 같은 것이다 (한 곳에서 만든다).
    assert section in build_final_prompt(domain, combo)


def _finish(**kwargs):
    state = service.start_session(SOURCE, model="m", demo_mode=True, **kwargs)
    while not state.done:
        state = service.submit_choice(state, state.pair.pair_id, "a")
    return state


def test_session_started_from_a_template_ends_with_it() -> None:
    template = template_library.get("tech-doc-en")
    state = _finish(domain_key="summarization", domain_path="domains/summarization.yaml", template_id=template.id)
    domain, estimator = service.current_estimate(state)
    prompt = service.final_prompt(domain, estimator, template_id=state.template_id)
    assert prompt.startswith(template.prompt.strip())
    assert "## 이 사용자의 선호" in prompt


def test_template_for_another_domain_is_refused() -> None:
    with pytest.raises(ValueError, match="summarization_ko"):
        service.start_session(SOURCE, "summarization", "domains/summarization.yaml",
                              model="m", demo_mode=True, template_id="meeting-notes-ko")


def test_api_lists_templates_and_uses_them(monkeypatch) -> None:
    import threading
    import urllib.request
    from http.server import ThreadingHTTPServer

    import api_server

    monkeypatch.setattr(api_server, "LIVE", False)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), api_server.ApiHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}/api"
    try:
        with urllib.request.urlopen(base + "/templates") as resp:
            listed = json.loads(resp.read().decode("utf-8"))["templates"]
        assert any(t["id"] == "bug-fix" and t["domain"] == "coding" for t in listed)

        def post(path, body):
            req = urllib.request.Request(base + path, json.dumps(body).encode(), {"Content-Type": "application/json"})
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read().decode("utf-8"))["session"]

        session = post("/sessions", {"domainKey": "coding", "sourceText": SOURCE, "templateId": "bug-fix"})
        while not session["done"]:
            session = post(f"/sessions/{session['session_id']}/choices",
                           {"pairId": session["pair"]["pair_id"], "chosen": "a"})
        assert session["prompt"].startswith(template_library.get("bug-fix").prompt.strip())
        # 바로 쓰기도 템플릿 기반 프롬프트를 내보낸다.
        copilot = next(e for e in session["exports"] if e["key"] == "copilot")
        assert session["prompt"] in copilot["content"]
    finally:
        srv.shutdown()
