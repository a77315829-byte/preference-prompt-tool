import pytest

from benchmarks.summary_agent_pilot.evaluate import length_pass, measurements, validate_facts, verbatim_units


def test_empty_output_cannot_pass_short_or_extractiveness():
    case = {"source": "A fact. Another fact.", "source_units": ["A fact.", "Another fact."],
            "source_words": 4, "profile": {"length": "short", "extractiveness": "normal"}}
    result = measurements("", case)
    assert not result["app_length_pass"]
    assert not result["app_overlap_proxy_pass"]
    assert not result["strict_source_unit_extraction"]


def test_verbatim_units_accept_whitespace_but_not_edited_or_partial_sentences():
    units = ["The vote is pending.", "It may pass on Friday."]
    assert verbatim_units("The vote is pending.\n\nIt may pass on Friday.", units)
    assert not verbatim_units("The vote is approved. It may pass on Friday.", units)
    assert not verbatim_units("The vote is pending", units)
    assert not verbatim_units("", units)


def test_high_proxy_can_disagree_with_literal_instruction():
    case = {"source": "The vote is pending.", "source_units": ["The vote is pending."],
            "source_words": 4, "profile": {"length": "short", "extractiveness": "high"}}
    result = measurements("The vote is pending.", case)
    assert result["bigram_overlap"] == 1
    assert not result["app_overlap_proxy_pass"]  # Diagnostic upper bound; not a factuality failure.
    assert result["strict_source_unit_extraction"]


def test_length_bounds_reject_empty_and_respect_edges():
    assert not length_pass(0, "short")
    assert length_pass(2, "short") and not length_pass(3, "short")
    assert length_pass(3, "normal") and length_pass(4, "normal")
    assert not length_pass(5, "normal") and length_pass(5, "long")


def test_facts_must_quote_actual_source():
    cases = [{"id": "S01", "source": "The vote is pending."}]
    facts = [{"id": "S01", "facts": [
        {"id": f"F{i}", "proposition": "Pending", "evidence": ["The vote is pending."]}
        for i in range(1, 4)
    ]}]
    validate_facts(cases, facts)
    facts[0]["facts"][0]["evidence"] = ["The vote passed."]
    with pytest.raises(AssertionError):
        validate_facts(cases, facts)
