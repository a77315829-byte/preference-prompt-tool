"""Focused boundary regressions without changing the frozen v1 artifacts."""
from __future__ import annotations

from itertools import product
from pathlib import Path

import pytest

from checks import summarization_grounded_v2 as checks
from engine.domain_loader import load_domain
from engine.generator import build_final_prompt, build_prompt

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("quote", ["'", '"', "’"])
def test_quoted_claim_keeps_lowercase_attribution(quote):
    source = f"{quote}The drug is safe!{quote} the company claimed. Regulators have not approved it."
    assert len(checks.split_sentences(source)) == 2
    assert checks.verbatim_sentences(f"{quote}The drug is safe!{quote}", source, "fully", {})[0] == 0
    assert checks.verbatim_sentences(f"{quote}The drug is safe!{quote} the company claimed.", source, "fully", {})[0] == 1


@pytest.mark.parametrize("starter", ["The trial", "It", "He", "She", "They", "We"])
def test_acronym_can_end_a_sentence_before_clear_starter(starter):
    second = f"{starter} remains unapproved."
    source = "The company operates in the U.S. " + second
    assert checks.split_sentences(source) == ["The company operates in the U.S.", second]
    assert checks.verbatim_sentences(second, source, "fully", {})[0] == 1
    assert checks.sentence_count(source, source, "short", {"max_sentences": 2})[0] == 1


@pytest.mark.parametrize("source", [
    "U.S. officials have not approved it.",
    "The U.S. State Department has not approved it.",
    "Dr. Smith spent $1.25 million at the U.N. office.",
])
def test_mid_sentence_acronym_and_titles_do_not_split(source):
    assert checks.split_sentences(source) == [source]
    assert checks.verbatim_sentences(source, source, "fully", {})[0] == 1


def test_independent_no_is_not_a_number_label():
    assert checks.split_sentences("No. We did not approve it.") == ["No.", "We did not approve it."]
    assert len(checks.split_sentences("Use No. 3 for this trial.")) == 1


def test_fact_edits_and_partial_sentences_still_fail():
    source = "The committee did not approve the $29 budget. It will vote again."
    for summary in ["The committee did approve the $29 budget.",
                    "The committee did not approve the $30 budget.",
                    "The committee did not approve the $29 budget"]:
        assert checks.verbatim_sentences(summary, source, "fully", {})[0] == 0
    assert checks.verbatim_sentences("The committee did not approve the $29 budget.", source, "fully", {})[0] == 1


def test_publisher_omission_is_not_permission_to_add_or_change_attribution():
    text = "The committee has not approved it."
    assert checks.verbatim_sentences(text, "(CNN)" + text, "fully", {})[0] == 1
    assert checks.verbatim_sentences("(cnn)" + text, "(CNN)" + text, "fully", {})[0] == 1
    assert checks.verbatim_sentences("(CNN)" + text, text, "fully", {})[0] == 0
    assert checks.verbatim_sentences("(CNN)" + text, "(The Hollywood Reporter)" + text, "fully", {})[0] == 0
    assert checks.verbatim_sentences(text, "News arrived. (CNN)" + text, "fully", {})[0] == 0


def test_korean_and_empty_output_smoke():
    source = "위원회는 승인하지 않았다. 예산은 29만 원이다."
    assert len(checks.split_sentences(source)) == 2
    assert checks.verbatim_sentences("예산은 29만 원이다.", source, "fully", {})[0] == 1
    assert checks.verbatim_sentences("예산은 30만 원이다.", source, "fully", {})[0] == 0
    assert checks.verbatim_sentences("", source, "fully", {})[0] == 0
    assert checks.sentence_count("", source, "short", {"max_sentences": 2})[0] == 0


@pytest.mark.parametrize("base", ["summarization_grounded", "summarization_ko_grounded"])
def test_v2_inherits_all_generation_prompts_without_changes(base):
    old = load_domain(ROOT / "domains" / f"{base}.yaml")
    new = load_domain(ROOT / "domains" / f"{base}_v2.yaml")
    assert new.name == old.name
    assert new.checks_module == "checks.summarization_grounded_v2"
    assert new.example_sources == old.example_sources
    for size, wording, language, team in product(
        ["short", "normal", "long"], ["normal", "high", "fully"], [None, "en"], [False, True]
    ):
        combo = {"length": size, "extractiveness": wording, "topic": "budget"}
        assert build_prompt(new, combo) == build_prompt(old, combo)
        assert build_final_prompt(new, combo, team=team, language=language) == build_final_prompt(old, combo, team=team, language=language)
