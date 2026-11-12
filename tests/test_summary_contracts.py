"""Source-grounded conflict decisions, stale input rejection, and no-API HTTP path."""
import json
import threading
import urllib.error
import urllib.request
from copy import deepcopy
from http.server import ThreadingHTTPServer

import pytest
import yaml

from summary_contracts import prepare_summary_contract, source_sentences
from tests.domain_inventory import DOMAIN_DIR, ENGINE_DOMAINS, SUPPORT_CONFIGS

SENTENCES = ["Gov. Han proposed a river trial.", "The trial would cost $29 million.",
             "The council has not approved the trial."]
SOURCE = " ".join(SENTENCES)


@pytest.mark.parametrize("language", ["en", "ko"])
def test_contract_support_config_has_its_own_complete_schema(language):
    assert SUPPORT_CONFIGS == {"summary_contract.yaml"}
    path = DOMAIN_DIR / "summary_contract.yaml"
    assert set(ENGINE_DOMAINS) | {path} == set(DOMAIN_DIR.glob("*.yaml"))
    assert path not in ENGINE_DOMAINS
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert config["version"] == 1
    assert set(config) == {"version", "en", "ko"}
    content = config[language]
    assert set(content) == {"heading", "rules", "policies", "task_heading", "task_instruction"}
    for key in ("heading", "task_heading", "task_instruction"):
        assert isinstance(content[key], str) and content[key].strip()
    assert isinstance(content["rules"], list) and content["rules"]
    assert all(isinstance(rule, str) and rule.strip() for rule in content["rules"])
    assert set(content["policies"]) == {"preserve", "expand", "rephrase", "keep_limits"}
    assert all(isinstance(rule, str) and rule.strip() for rule in content["policies"].values())


def request(**updates):
    body = {"domainKey": "summarization", "profile": {"length": "short", "extractiveness": "fully", "topic": ""},
            "sourceText": SOURCE, "requiredSentences": SENTENCES, "resolution": None}
    body.update(updates)
    return body


def test_collision_requires_explicit_choice_and_never_returns_usable_prompt():
    body = request(); before = deepcopy(body)
    result = prepare_summary_contract(body)
    assert body == before
    assert result["status"] == "needs_resolution"
    assert result["conflict"]["required_sentences"] == 3
    assert result["conflict"]["max_sentences"] == 2
    assert result["prompts"] == result["task_requests"] == {}
    assert result["effective_profile"] == result["original_profile"]


@pytest.mark.parametrize("resolution,length,wording,policy", [
    ("expand", "normal", "fully", "all_required"),
    ("rephrase", "short", "normal", "all_required"),
    ("keep_limits", "short", "fully", "prioritize_with_omission"),
])
def test_only_explicit_authorized_constraint_changes(resolution, length, wording, policy):
    result = prepare_summary_contract(request(resolution=resolution))
    assert result["status"] == "ready"
    assert result["original_profile"]["length"] == "short"
    assert result["original_profile"]["extractiveness"] == "fully"
    assert result["effective_profile"] == {"length": length, "extractiveness": wording, "topic": ""}
    for language in ["en", "ko"]:
        assert SOURCE not in result["prompts"][language]
        assert all(s not in result["prompts"][language] for s in SENTENCES)
        assert SOURCE in result["task_requests"][language]
        assert f'"coverage_policy": "{policy}"' in result["task_requests"][language]
    assert any("다른 원문" in text for text in result["notices"])


def test_wider_conflict_expands_to_long_and_no_upper_limit_is_invented():
    sentences = [f"Item {n} is pending." for n in range(6)]
    body = request(sourceText=" ".join(sentences), requiredSentences=sentences,
                   profile={"length": "normal", "extractiveness": "fully"}, resolution="expand")
    result = prepare_summary_contract(body)
    assert result["conflict"]["max_sentences"] == 4
    assert result["effective_profile"]["length"] == "long"
    assert "five or more" in result["prompts"]["en"]


def test_no_semantic_feasibility_claim_for_rephrasing():
    result = prepare_summary_contract(request(profile={"length": "short", "extractiveness": "normal"}))
    assert result["status"] == "ready" and result["conflict"] is None
    assert any("판별할 수 없습니다" in text for text in result["notices"])


def test_source_order_and_whitespace_are_canonical_not_click_order():
    result = prepare_summary_contract(request(requiredSentences=[SENTENCES[2], "Gov.  Han proposed a river trial."], resolution=None))
    assert result["status"] == "ready"
    assert result["required_sentences"] == [SENTENCES[0], SENTENCES[2]]


def test_repeated_source_sentence_is_not_a_second_required_fact():
    result = prepare_summary_contract(request(sourceText=SOURCE+" "+SENTENCES[0], requiredSentences=SENTENCES[:2]))
    assert len(result["available_sentences"]) == 3
    assert result["conflict"] is None


@pytest.mark.parametrize("updates", [
    {"requiredSentences": ["Han proposed a river trial."]},
    {"requiredSentences": [SENTENCES[0], SENTENCES[0]]},
    {"requiredSentences": [SENTENCES[0]+" "+SENTENCES[1]]},
    {"requiredSentences": ["Gov. Han approved a river trial."]},
    {"sourceText": "The source was replaced."},
    {"requiredSentences": SENTENCES*3},
    {"requiredSentences": "not a list"},
    {"sourceText": "x"*12001},
    {"sourceText": " "},
    {"domainKey": "coding"},
    {"domainKey": []},
    {"profile": {"length": None, "extractiveness": "fully"}},
    {"profile": {"length": "short", "extractiveness": "fully", "specificity": "high"}},
    {"profile": {"length": "short", "extractiveness": "fully", "topic": ["x"]}},
    {"resolution": "silently_relax"},
    {"requiredSentences": [], "resolution": "expand"},
])
def test_invalid_or_stale_requests_are_rejected(updates):
    with pytest.raises(ValueError):
        prepare_summary_contract(request(**updates))


def test_korean_source_and_publisher_normalization():
    source = "(CNN)시범 사업이 제안됐다. 비용은 29억 원이다. 아직 승인하지 않았다."
    selected = source_sentences(source)
    result = prepare_summary_contract(request(domainKey="summarization_ko", sourceText=source,
                                              requiredSentences=selected, resolution="rephrase"))
    assert result["status"] == "ready"
    assert "in Korean" in result["prompts"]["en"]
    assert "아직 승인하지 않았다." in result["task_requests"]["ko"]


@pytest.fixture
def server(monkeypatch):
    import api_server
    import service
    def forbidden(*args, **kwargs):
        pytest.fail("The contract path must not call generation or optimization")
    monkeypatch.setattr(service, "generate_all", forbidden)
    monkeypatch.setattr(service, "optimize", forbidden)
    # Exercise the no-model endpoint even if the rest of the server is live.
    monkeypatch.setattr(api_server, "LIVE", True)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), api_server.ApiHandler)
    thread = threading.Thread(target=srv.serve_forever, daemon=True); thread.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown(); srv.server_close(); thread.join()


def post(server, body, headers=None):
    req = urllib.request.Request(server+"/api/summary-contract", json.dumps(body).encode(),
                                 {"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, json.load(error)


def test_http_collision_then_explicit_resolution_without_model(server):
    status, body = post(server, request())
    assert status == 200 and body["status"] == "needs_resolution"
    status, body = post(server, request(resolution="expand"))
    assert status == 200 and body["effective_profile"]["length"] == "normal"
    status, body = post(server, request(requiredSentences=["Invented fact."]))
    assert status == 400 and "error" in body


def test_http_cross_site_request_is_rejected(server):
    status, _ = post(server, request(), {"Origin": "https://unrelated.example"})
    assert status == 403
