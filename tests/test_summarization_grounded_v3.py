"""Boundary corrections and inherited contracts, with no model/API calls."""
from __future__ import annotations

from itertools import product
from pathlib import Path

import pytest

from checks import summarization_grounded_v2 as previous
from checks import summarization_grounded_v3 as checks
from engine.domain_loader import load_domain
from engine.generator import build_final_prompt, build_prompt

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("sentence", [
    "Gov. David Ige warned that the storm could change direction.",
    "Isabela Gov. Faustino Dry III said the impact was unknown.",
    "Rep. Kathleen Rice requested another review.",
    "Gov. O'Connor has not approved it.",
    "Rep. J. Smith said the proposal may fail.",
])
def test_public_title_before_person_does_not_add_a_sentence(sentence):
    text = sentence + " The decision is pending."
    assert checks.split_sentences(text) == [sentence, "The decision is pending."]
    assert checks.sentence_count(text, text, "short", {"max_sentences": 2})[0] == 1
    assert checks.verbatim_sentences(sentence, text, "fully", {})[0] == 1


@pytest.mark.parametrize("title", ["Gov.", "Rep."])
@pytest.mark.parametrize("next_sentence", ["The vote ended.", "It failed.", "They resigned.", "Now we wait."])
def test_public_title_can_end_an_utterance(title, next_sentence):
    first = "The form lists the abbreviation " + title
    assert checks.split_sentences(first + " " + next_sentence) == [first, next_sentence]
    assert checks.split_sentences(first) == [first]
    assert checks.verbatim_sentences(next_sentence, first + " " + next_sentence, "fully", {})[0] == 1


@pytest.mark.parametrize("sentence", [
    "E! plans to air a new series in July.",
    "The announcement says E! will air a new series in July.",
    "E! executive Jeff Olde praised the proposal.",
    "E! News reported that the date remains uncertain.",
    "According to E! Jennifer Finney Boylan will advise the series.",
])
def test_broadcaster_token_inside_sentence(sentence):
    text = sentence + " The date is not confirmed."
    assert checks.split_sentences(text) == [sentence, "The date is not confirmed."]
    assert checks.verbatim_sentences(sentence, text, "fully", {})[0] == 1


@pytest.mark.parametrize("first,second", [
    ("The show airs on E!", "The date is unknown."),
    ("The show airs on E!", '"It may change," the producer said.'),
    ("Choose E!", "Then submit the form."),
    ("The answer is E!", "Now continue."),
])
def test_broadcaster_or_letter_can_end_a_sentence(first, second):
    assert checks.split_sentences(first + " " + second) == [first, second]


def test_new_title_and_broadcaster_masks_keep_original_offsets():
    text = "E! executive J. Smith met Gov. Ige. Rep. Rice asked for $1.25 million."
    assert checks.split_sentences(text) == [
        "E! executive J. Smith met Gov. Ige.",
        "Rep. Rice asked for $1.25 million.",
    ]
    assert checks.verbatim_sentences(text, text, "fully", {})[0] == 1
    assert checks.verbatim_sentences(text.replace("$1.25", "$1.35"), text, "fully", {})[0] == 0


@pytest.mark.parametrize("partial,source", [
    ("Gov.", "Gov. Ige said no."),
    ("Rep.", "Rep. Rice declined."),
    ("E!", "E! plans to air the show."),
    ("Ige said no.", "Gov. Ige said no."),
    ("E! plans to air the show", "E! plans to air the show."),
    ("Gov. Ige said yes.", "Gov. Ige said no."),
])
def test_title_and_channel_fixes_do_not_allow_fragments_or_edits(partial, source):
    assert checks.verbatim_sentences(partial, source, "fully", {})[0] == 0


@pytest.mark.parametrize("source,expected", [
    ('Dr. Smith works for the U.S. agency. It spent $1.25 million. "Why?" she asked.', 3),
    ('She said, "Stop." The vote paused.', 2),
    ("'The drug is safe!' the company claimed. Regulators have not approved it.", 2),
    ("The company operates in the U.S. The trial remains unapproved.", 2),
    ("The U.S. State Department has not approved it.", 1),
    ("Use No. 3 for this vote. No. We did not approve it.", 3),
    ("위원회는 승인하지 않았다. 예산은 29만 원이다.", 2),
])
def test_previous_boundary_invariants(source, expected):
    assert len(checks.split_sentences(source)) == expected
    assert checks.split_sentences(source) == previous.split_sentences(source)


def test_attribution_publisher_and_empty_summary_rules_remain():
    source = "(CNN)'It is safe!' the company claimed. Regulators have not approved it."
    whole = "'It is safe!' the company claimed."
    assert checks.verbatim_sentences(whole, source, "fully", {})[0] == 1
    assert checks.verbatim_sentences("'It is safe!'", source, "fully", {})[0] == 0
    assert checks.verbatim_sentences("(cnn)" + whole, source, "fully", {})[0] == 1
    assert checks.verbatim_sentences("(CNN)" + whole, whole, "fully", {})[0] == 0
    assert checks.verbatim_sentences("(The Hollywood Reporter)" + whole, source, "fully", {})[0] == 0
    assert checks.verbatim_sentences("", source, "fully", {})[0] == 0
    assert checks.sentence_count("", source, "short", {"max_sentences": 2})[0] == 0


@pytest.mark.parametrize("name", ["summarization_grounded", "summarization_ko_grounded"])
def test_v3_only_changes_checker_not_prompts_or_targets(name):
    old = load_domain(ROOT / "domains" / f"{name}_v2.yaml")
    new = load_domain(ROOT / "domains" / f"{name}_v3.yaml")
    assert new.name == old.name
    assert new.checks_module == "checks.summarization_grounded_v3"
    assert new.example_sources == old.example_sources
    for size, wording, language, team in product(
        ["short", "normal", "long"], ["normal", "high", "fully"], [None, "en"], [False, True]
    ):
        combo = {"length": size, "extractiveness": wording, "topic": "budget"}
        assert build_prompt(new, combo) == build_prompt(old, combo)
        assert build_final_prompt(new, combo, team=team, language=language) == build_final_prompt(old, combo, team=team, language=language)
        for axis, value in combo.items():
            assert new.axis(axis).check_for(value) == old.axis(axis).check_for(value)
