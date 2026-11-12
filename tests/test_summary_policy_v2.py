"""Summary input boundaries and explicit, feasible conflict choices; no models."""
from copy import deepcopy
from http.server import ThreadingHTTPServer
import json
import threading
import urllib.error
import urllib.request

import pytest

from summary_contracts import prepare_summary_contract as frozen_contract
from summary_contracts_v2 import prepare_summary_contract
from summary_input_policy import validate_summary_source


def request(count=2, length="long", **changes):
    sentences = [f"Item {n} remains pending." for n in range(count)]
    value = {"domainKey": "summarization", "sourceText": " ".join(sentences),
             "profile": {"length": length, "extractiveness": "fully", "topic": ""},
             "requiredSentences": sentences, "resolution": None}
    value.update(changes)
    return value


@pytest.mark.parametrize("value", [None, 42, True, [], {}, "", " \n\t", "x" * 12001, "🙂" * 12001, " " * 12000 + "x"], ids=["null", "number", "bool", "list", "object", "empty", "blank", "ascii-over", "emoji-over", "space-over"])
def test_summary_source_rejects_invalid_input_without_coercion_or_truncation(value):
    with pytest.raises(ValueError, match="1~12,000"):
        validate_summary_source(value)


@pytest.mark.parametrize("value", ["가" * 12000, "🙂" * 12000, " " + "x" * 11998 + " "], ids=["korean-limit", "emoji-limit", "space-limit"])
def test_limit_counts_code_points_and_whitespace(value):
    assert validate_summary_source(value) == value.strip()


@pytest.mark.parametrize("domain", ["summarization", "summarization_ko"])
@pytest.mark.parametrize("length,count", [("normal", 2), ("long", 2), ("long", 4)])
def test_too_few_distinct_sentences_requires_a_choice(domain, length, count):
    body = request(count, length, domainKey=domain)
    original = deepcopy(body)
    result = prepare_summary_contract(body)
    assert body == original
    assert result["version"] == 2 and result["status"] == "needs_resolution"
    assert result["conflict"]["kind"] == "source_under_minimum"
    assert result["conflict"]["available_sentences"] == count
    assert result["prompts"] == result["task_requests"] == {}
    assert result["available_resolutions"] == ["shorten", "rephrase"]
    # The older experiment path intentionally retains its original behavior.
    assert frozen_contract(body)["status"] == "ready"


@pytest.mark.parametrize("count,expected", [(1, "short"), (2, "short"), (3, "normal"), (4, "normal")])
def test_shortening_preserves_extraction_topic_and_every_requested_passage(count, expected):
    body = request(count, profile={"length": "long", "extractiveness": "fully", "topic": "schedule"}, resolution="shorten")
    result = prepare_summary_contract(body)
    assert result["status"] == "ready"
    assert result["effective_profile"] == {"length": expected, "extractiveness": "fully", "topic": "schedule"}
    assert result["original_profile"] == body["profile"]
    assert result["required_sentences"] == body["requiredSentences"]
    assert result["coverage_policy"] == "all_required"
    for language in ["en", "ko"]:
        assert body["sourceText"] not in result["prompts"][language]
        assert body["sourceText"] in result["task_requests"][language]
    assert "smaller sentence budget" in result["prompts"]["en"]
    assert "No condition has been relaxed" not in result["prompts"]["en"]
    assert "분량 축소" in result["prompts"]["ko"]


def test_rephrasing_changes_only_wording_and_does_not_claim_guaranteed_coverage():
    result = prepare_summary_contract(request(resolution="rephrase"))
    assert result["effective_profile"] == {"length": "long", "extractiveness": "normal", "topic": ""}
    assert any("실제 요약에서 확인" in notice for notice in result["notices"])
    assert result["coverage_policy"] == "all_required"


@pytest.mark.parametrize("source", ["Incomplete source without a terminator", "Gov. Han", "미완성 원문"])
def test_no_complete_sentence_does_not_offer_a_fake_shortening_fix(source):
    result = prepare_summary_contract(request(sourceText=source, requiredSentences=[]))
    assert result["status"] == "needs_resolution"
    assert result["available_resolutions"] == ["rephrase"]
    with pytest.raises(ValueError):
        prepare_summary_contract(request(sourceText=source, requiredSentences=[], resolution="shorten"))


def test_repetition_and_abbreviations_do_not_inflate_available_sentences():
    source = "Gov. Han proposed a trial. " * 6
    result = prepare_summary_contract(request(sourceText=source, requiredSentences=["Gov. Han proposed a trial."]))
    assert result["conflict"]["available_sentences"] == 1
    assert result["status"] == "needs_resolution"


@pytest.mark.parametrize("resolution", ["expand", "keep_limits"])
def test_inapplicable_resolution_is_rejected_for_a_short_source(resolution):
    with pytest.raises(ValueError, match="현재 충돌"):
        prepare_summary_contract(request(resolution=resolution))


@pytest.mark.parametrize("resolution", ["shorten", "expand", "rephrase", "keep_limits"])
def test_stale_resolution_cannot_silently_change_a_nonconflicting_request(resolution):
    with pytest.raises(ValueError, match="현재 충돌"):
        prepare_summary_contract(request(5, resolution=resolution))


@pytest.mark.parametrize("resolution,expected_length,expected_wording,coverage", [
    ("expand", "normal", "fully", "all_required"),
    ("rephrase", "short", "normal", "all_required"),
    ("keep_limits", "short", "fully", "prioritize_with_omission"),
])
def test_original_over_budget_conflict_still_changes_only_authorized_conditions(resolution, expected_length, expected_wording, coverage):
    result = prepare_summary_contract(request(3, "short", resolution=resolution))
    assert result["effective_profile"] == {"length": expected_length, "extractiveness": expected_wording, "topic": ""}
    assert result["coverage_policy"] == coverage
    assert result["conflict"]["kind"] == "required_over_budget"
    assert "shorten" not in result["available_resolutions"]
    assert f'"coverage_policy": "{coverage}"' in result["task_requests"]["en"]


def test_topic_has_same_code_point_policy_as_source():
    body = request(5, profile={"length": "long", "extractiveness": "fully", "topic": "🙂" * 300})
    assert prepare_summary_contract(body)["status"] == "ready"
    body["profile"]["topic"] += "🙂"
    with pytest.raises(ValueError, match="300"):
        prepare_summary_contract(body)


@pytest.fixture
def server(monkeypatch):
    import api_server
    import service
    monkeypatch.setattr(api_server, "LIVE", False)
    def forbidden(*args, **kwargs):
        pytest.fail("Summary policy tests must not call models")
    monkeypatch.setattr(service, "generate_all", forbidden)
    monkeypatch.setattr(service, "optimize", forbidden)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), api_server.ApiHandler)
    worker = threading.Thread(target=srv.serve_forever, daemon=True)
    worker.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown(); srv.server_close(); worker.join()


def post(server, path, body):
    req = urllib.request.Request(server + path, json.dumps(body).encode(), {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, json.load(error)


@pytest.mark.parametrize("source", ["x" * 12001, "🙂" * 12001, {"text": "not a string"}], ids=["ascii-over", "emoji-over", "object"])
def test_both_http_entry_points_reject_before_any_live_usage(server, monkeypatch, source):
    import api_server
    import service
    def forbidden(*args, **kwargs):
        pytest.fail("Invalid input must be rejected before quota or generation")
    monkeypatch.setattr(api_server, "LIVE", True)
    monkeypatch.setattr(api_server, "_live_key_available", forbidden)
    monkeypatch.setattr(service, "start_session", forbidden)
    for domain in ["summarization", "summarization_ko"]:
        body = request(domainKey=domain, sourceText=source)
        session_status, session = post(server, "/api/sessions", body)
        contract_status, contract = post(server, "/api/summary-contract", body)
        assert session_status == contract_status == 400
        assert session["error"] == contract["error"]


@pytest.mark.parametrize("source", ["가" * 11999 + ".", "🙂" * 11999 + "."], ids=["korean-limit", "emoji-limit"])
def test_both_http_entry_points_preserve_the_entire_boundary_source(server, source):
    body = request(sourceText=source, requiredSentences=[], profile={"length": "short", "extractiveness": "fully"})
    status, session = post(server, "/api/sessions", body)
    assert status == 201 and session["session"]["source_text"] == source
    status, contract = post(server, "/api/summary-contract", body)
    assert status == 200 and contract["version"] == 2 and contract["status"] == "ready"
    assert source in contract["task_requests"]["en"]


def test_http_resolution_and_legacy_coding_route(server):
    status, body = post(server, "/api/summary-contract", request())
    assert status == 200 and body["status"] == "needs_resolution"
    status, body = post(server, "/api/summary-contract", request(resolution="shorten"))
    assert status == 200 and body["effective_profile"]["length"] == "short"
    status, body = post(server, "/api/sessions", {"domainKey": "coding", "sourceText": "A React checklist"})
    assert status == 201 and body["session"]["domain_key"] == "coding"
    assert body["session"]["demo_mode"] is True
