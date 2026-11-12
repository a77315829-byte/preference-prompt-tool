"""Synthetic contract/evidence/seal checks; no real benchmark sources or models."""
from copy import deepcopy

import pytest

from benchmarks.summary_contract_revision import run
from summary_contracts import prepare_summary_contract


SOURCE_SENTENCES = [
    "The council proposes a trial.",
    "The trial would cost $29.",
    "The trial is not approved.",
]


def synthetic_packet_and_review():
    text = "The council proposes a trial costing $29, but it is not approved."
    evidence = ["The council proposes a trial", "$29", "not approved"]
    packet = [{
        "output_id": "S1", "case_id": "synthetic", "source": " ".join(SOURCE_SENTENCES),
        "summary": text, "target": {"length": "short", "extractiveness": "normal", "topic": ""},
        "coverage_policy": "all_required",
        "required_passages": [{"id": f"P{i}", "text": s} for i, s in enumerate(SOURCE_SENTENCES, 1)],
        "key_facts": [{"id": f"F{i}", "proposition": s, "evidence": [s]}
                      for i, s in enumerate(SOURCE_SENTENCES, 1)],
    }]
    review = [{
        "output_id": "S1", "sentence_count": 1, "wording_pass": True,
        "wording_reason": "Rephrases and combines source information.",
        "response_kind": "summary",
        "facts": [{"id": f"F{i}", "preserved": True, "summary_evidence": [q],
                   "reason": "The proposition is present."} for i, q in enumerate(evidence, 1)],
        "priorities": [{"id": f"P{i}", "preserved": True, "summary_evidence": [q],
                        "reason": "The selected information is present."} for i, q in enumerate(evidence, 1)],
        "issues": [],
    }]
    return packet, review


@pytest.mark.parametrize("resolution,length_phrase,wording_phrase", [
    ("expand", "Use three or four sentences.", "Use only complete source sentences"),
    ("rephrase", "Use one or two sentences.", "Mostly rewrite in your own words"),
    ("keep_limits", "Use one or two sentences.", "Use only complete source sentences"),
])
def test_manual_baseline_uses_authorized_effective_conditions(resolution, length_phrase, wording_phrase):
    result = prepare_summary_contract({
        "domainKey": "summarization",
        "profile": {"length": "short", "extractiveness": "fully", "topic": ""},
        "sourceText": " ".join(SOURCE_SENTENCES), "requiredSentences": SOURCE_SENTENCES,
        "resolution": resolution,
    })
    prompt = run.manual_prompt(result["effective_profile"])
    assert length_phrase in prompt and wording_phrase in prompt
    assert "do not silently change" in prompt
    assert "request clarification" in prompt
    assert "not approved" not in prompt  # no synthetic source answer leaked into reusable instructions


def test_manual_baseline_retains_explicit_focus():
    prompt = run.manual_prompt({"length": "normal", "extractiveness": "high", "topic": "funding and unresolved approval"})
    assert "funding and unresolved approval" in prompt
    assert "Use three or four sentences." in prompt
    assert "there is no upper limit" in prompt


def test_valid_exact_evidence_is_accepted_without_mutation():
    packet, rows = synthetic_packet_and_review()
    before = deepcopy((packet, rows))
    run.validate_extra(rows, packet)
    assert (packet, rows) == before


@pytest.mark.parametrize("kind", ["source_only", "empty", "whitespace", "string", "extra_id", "duplicate_id"])
def test_priority_evidence_and_identity_must_match_the_anonymous_output(kind):
    packet, rows = synthetic_packet_and_review()
    item = rows[0]["priorities"][0]
    if kind == "source_only":
        item["summary_evidence"] = [SOURCE_SENTENCES[1]]  # in source, absent from actual response
    elif kind == "empty":
        item["summary_evidence"] = []
    elif kind == "whitespace":
        item["summary_evidence"] = [" "]
    elif kind == "string":
        item["summary_evidence"] = "$29"
    elif kind == "extra_id":
        item["id"] = "P4"
    else:
        item["id"] = "P2"
    with pytest.raises(AssertionError):
        run.validate_extra(rows, packet)


@pytest.mark.parametrize("field", ["priority", "fact", "wording", "sentence_count"])
def test_truthy_values_cannot_replace_typed_review_fields(field):
    packet, rows = synthetic_packet_and_review()
    if field == "priority":
        rows[0]["priorities"][0]["preserved"] = 1
    elif field == "fact":
        rows[0]["facts"][0]["preserved"] = "yes"
    elif field == "wording":
        rows[0]["wording_pass"] = 1
    else:
        rows[0]["sentence_count"] = True
    with pytest.raises(AssertionError):
        run.validate_extra(rows, packet)


def test_factual_flag_cannot_cite_a_different_source():
    packet, rows = synthetic_packet_and_review()
    rows[0]["issues"] = [{"summary_quote": "$29", "reason": "A proposed quantity issue.",
                          "source_evidence": ["The trial would cost $30."]}]
    with pytest.raises(AssertionError):
        run.validate_extra(rows, packet)


def test_unknown_response_kind_is_not_silently_scored_as_summary():
    packet, rows = synthetic_packet_and_review()
    rows[0]["response_kind"] = "successful"
    with pytest.raises(AssertionError):
        run.validate_extra(rows, packet)


def test_clarification_is_a_distinct_permitted_response_kind():
    packet, rows = synthetic_packet_and_review()
    packet[0]["summary"] = "Which constraint should I relax?"
    rows[0].update(response_kind="clarification", wording_pass=False,
                   wording_reason="Asks a question rather than summarizing.")
    for item in rows[0]["facts"] + rows[0]["priorities"]:
        item.update(preserved=False, summary_evidence=[], reason="No source information summarized.")
    run.validate_extra(rows, packet)


def test_zero_sentence_fragment_keeps_its_original_grade():
    packet, rows = synthetic_packet_and_review()
    packet[0]["summary"] = "Unavailable"
    rows[0].update(response_kind="other", sentence_count=0, wording_pass=False,
                   wording_reason="A fragment with no attempted summary.")
    for item in rows[0]["facts"] + rows[0]["priorities"]:
        item.update(preserved=False, summary_evidence=[], reason="No source information summarized.")
    before = deepcopy((packet, rows))
    run.validate_extra(rows, packet)
    assert (packet, rows) == before
    assert rows[0]["sentence_count"] == 0


def test_zero_sentence_attempted_summary_is_rejected():
    packet, rows = synthetic_packet_and_review()
    rows[0]["sentence_count"] = 0
    with pytest.raises(AssertionError):
        run.validate_extra(rows, packet)


@pytest.mark.parametrize("kind", ["summary", "clarification", "other"])
def test_negative_sentence_count_is_never_valid(kind):
    packet, rows = synthetic_packet_and_review()
    rows[0].update(response_kind=kind, sentence_count=-1)
    with pytest.raises(AssertionError):
        run.validate_extra(rows, packet)


def test_seal_detects_even_same_length_content_change(tmp_path, monkeypatch):
    monkeypatch.setattr(run, "ROOT", tmp_path)
    artifact = tmp_path / "inputs.json"
    artifact.write_text('{"condition":"short"}', encoding="utf-8")
    manifest = tmp_path / "seal.json"
    run.seal(manifest, [artifact])
    run.check_seal(manifest)
    artifact.write_text('{"condition":"other"}', encoding="utf-8")
    with pytest.raises(AssertionError):
        run.check_seal(manifest)


def test_empty_manifest_cannot_pass_integrity_check(tmp_path, monkeypatch):
    monkeypatch.setattr(run, "ROOT", tmp_path)
    manifest = tmp_path / "seal.json"
    run.write(manifest, {})
    with pytest.raises(AssertionError):
        run.check_seal(manifest)


def test_first_response_writer_refuses_overwrite(tmp_path):
    output = tmp_path / "first.json"
    run.write(output, {"summary": "First."})
    with pytest.raises(FileExistsError):
        run.write(output, {"summary": "Improved after grading."})
    assert run.read(output) == {"summary": "First."}


def test_reference_overlap_counts_order_and_repetition_not_semantic_truth():
    assert run.lcs_f1("Alpha beta gamma", "alpha gamma") == pytest.approx(.8)
    assert run.lcs_f1("alpha beta gamma", "gamma alpha beta") == pytest.approx(2 / 3)
    assert run.lcs_f1("x x y", "x y") == pytest.approx(.8)
    assert run.lcs_f1("alpha", "beta") == 0
    assert run.lcs_f1("", "beta") == 0
