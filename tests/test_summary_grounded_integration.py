"""New sessions export grounded rules while original research files remain usable."""
from pathlib import Path

import pytest

import api_server
import service
from engine.domain_loader import load_domain
from engine.generator import build_final_prompt


@pytest.mark.parametrize("key,source,language_phrase", [
    ("summarization", "The council approved a trial. It costs $20. The trial lasts two weeks. A review is pending. No permanent plan was approved. Residents can comment.", "in English"),
    ("summarization_ko", "시가 시범 사업을 승인했다. 비용은 20억 원이다. 기간은 2주다. 검토가 남아 있다. 정식 사업은 아직 승인하지 않았다. 주민 의견을 받는다.", "in Korean"),
])
def test_new_demo_session_exports_grounded_rules_without_model_calls(monkeypatch, key, source, language_phrase):
    def forbidden(*args, **kwargs):
        pytest.fail("This integration test must not call a model")
    monkeypatch.setattr(service, "generate_all", forbidden)
    path = api_server._domain_path(key)
    assert "grounded" in Path(path).stem
    state = service.start_session(source, key, path, model="unused", demo_mode=True)
    while not state.done:
        state = service.submit_choice(state, state.pair.pair_id, "a")
    payload = api_server._state_payload(state)
    assert "Source fidelity takes priority" in payload["prompts"]["en"]
    assert "central subject and event" in payload["prompts"]["en"]
    assert language_phrase in payload["prompts"]["en"]
    assert "사실 관계가 표현 선호보다 우선" in payload["prompts"]["ko"]
    assert len(state.history) <= 8


def test_legacy_export_still_available_and_coding_route_unchanged():
    combo = {"length": "short", "extractiveness": "fully", "topic": ""}
    original = build_final_prompt(load_domain("domains/summarization.yaml"), combo, language="en")
    revised = build_final_prompt(load_domain(api_server._domain_path("summarization")), combo, language="en")
    assert "Follow the preferences above" in original
    assert "Source fidelity takes priority" in revised
    assert Path(api_server._domain_path("coding")).name == "coding.yaml"


def test_new_checks_do_not_accept_near_copy_with_reversed_fact():
    domain = load_domain(api_server._domain_path("summarization"))
    source = "The council did not approve the permanent plan. The trial costs $20."
    from checks.summarization_grounded import verbatim_sentences
    assert domain.axis("extractiveness").check_for("fully").fn == "verbatim_sentences"
    assert verbatim_sentences("The council did approve the permanent plan.", source, "fully", {})[0] == 0
