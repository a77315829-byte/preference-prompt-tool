"""Regression cases for the versioned product summary contract, without APIs."""
from __future__ import annotations

from pathlib import Path

import pytest

from checks import summarization_grounded as checks
from engine.domain_loader import load_domain
from engine.generator import build_final_prompt

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("changed", [
    "The council did approve the plan.",
    "The council did not approve the plans.",
    "The council did not approve the plan!",
])
def test_fully_rejects_near_identical_edits(changed):
    source = "The council did not approve the plan. It will vote again."
    assert checks.verbatim_sentences(changed, source, "fully", {})[0] == 0


def test_fully_rejects_changed_amount_and_partial_sentence():
    source = "The budget is $29 for seven days. It starts Monday."
    assert checks.verbatim_sentences("The budget is $30 for seven days.", source, "fully", {})[0] == 0
    assert checks.verbatim_sentences("The budget is $29", source, "fully", {})[0] == 0


@pytest.mark.parametrize("prefix", ["(CNN)", "(cnn)", "(The Hollywood Reporter)"])
def test_fully_allows_only_specified_leading_publisher_and_whitespace(prefix):
    source = prefix + "The agency rejected it. It will vote again."
    assert checks.verbatim_sentences("The agency rejected it.\n\nIt will vote again.", source, "fully", {})[0] == 1
    assert checks.verbatim_sentences(prefix + "The agency rejected it.", source, "fully", {})[0] == 1


def test_publisher_is_not_removed_from_middle_or_arbitrary_source():
    assert checks.verbatim_sentences("The agency rejected it.", "(Reuters)The agency rejected it.", "fully", {})[0] == 0
    source = "News arrived. (CNN)The agency rejected it."
    assert checks.verbatim_sentences("The agency rejected it.", source, "fully", {})[0] == 0
    assert checks.verbatim_sentences("The agency rejected it.", "(CNN)(CNN)The agency rejected it.", "fully", {})[0] == 0


def test_optional_publisher_cannot_be_added_or_replaced():
    text = "The agency rejected it."
    assert checks.verbatim_sentences("(CNN)" + text, text, "fully", {})[0] == 0
    assert checks.verbatim_sentences("(CNN)" + text, "(The Hollywood Reporter)" + text, "fully", {})[0] == 0


def test_fully_cannot_drop_attribution_inside_sentence():
    source = 'Officials said, "The plan may pass." It remains undecided.'
    assert checks.verbatim_sentences('"The plan may pass."', source, "fully", {})[0] == 0
    assert checks.verbatim_sentences('Officials said, "The plan may pass."', source, "fully", {})[0] == 1


def test_sentence_boundaries_respect_abbreviations_decimals_and_quotes():
    text = 'Dr. Smith works for the U.S. agency. It spent $1.25 million. "Why?" she asked.'
    assert len(checks.split_sentences(text)) == 3
    assert len(checks.split_sentences('She said, "Stop." The vote paused.')) == 2
    assert len(checks.split_sentences('No. We did not vote.')) == 2
    assert len(checks.split_sentences('Use No. 3 for this vote.')) == 1


@pytest.mark.parametrize("fn", [checks.sentence_count, checks.lexical_overlap, checks.verbatim_sentences])
def test_empty_summary_never_passes(fn):
    assert fn(" \n ", "The budget is $29.", "short", {"max_sentences": 2, "max_overlap": .5})[0] == 0


def test_high_reuse_does_not_penalize_perfect_copy():
    domain = load_domain(ROOT / "domains/summarization_grounded.yaml")
    spec = domain.axis("extractiveness").check_for("high")
    text = "The council will vote on Monday."
    score, feedback = checks.lexical_overlap(text, text, "high", spec.target)
    assert score == 1
    assert "max_overlap" not in spec.target
    assert "참고 지표" in feedback and "의미·사실성 판정 아님" in feedback


def test_korean_form_and_proxy_smoke(monkeypatch):
    from checks import summarization_ko
    monkeypatch.setattr(summarization_ko, "_backend", "regex")
    text = "위원회는 월요일에 표결한다. 예산은 29만 원이다."
    assert len(checks.split_sentences(text)) == 2
    assert checks.verbatim_sentences(text, text, "fully", {})[0] == 1
    assert checks.verbatim_sentences(text.replace("29", "30"), text, "fully", {})[0] == 0
    score, feedback = checks.lexical_overlap(text, text, "high", {"min_overlap": .5, "language": "ko"})
    assert score == 1 and "참고 지표" in feedback


@pytest.mark.parametrize("name,identity", [
    ("summarization_grounded", "summarization"),
    ("summarization_ko_grounded", "summarization_ko"),
])
def test_domains_preserve_identity_topics_examples_and_language(name, identity):
    domain = load_domain(ROOT / "domains" / f"{name}.yaml")
    assert domain.name == identity
    assert len(domain.example_sources) == 3
    assert domain.axis("topic").check_for("budget").fn == "keyword_presence"
    assert domain.axis("extractiveness").check_for("fully").fn == "verbatim_sentences"
    for language in (None, "en"):
        prompt = build_final_prompt(domain, {"length": "short", "extractiveness": "fully", "topic": "budget"}, language=language)
        assert "budget" in prompt
        assert "The Hollywood Reporter" in prompt
        expected = ("Korean" if identity.endswith("_ko") else "English") if language else ("한국어" if identity.endswith("_ko") else "영어")
        assert expected in prompt


def test_old_definition_keeps_historic_upper_bound():
    domain = load_domain(ROOT / "domains/summarization.yaml")
    assert domain.axis("extractiveness").check_for("high").target["max_overlap"] == .75
    assert domain.axis("extractiveness").check_for("fully").fn == "lexical_overlap"
