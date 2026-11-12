"""Demo summaries select whole sentences without truncating title abbreviations."""

import pytest

from demos import summarization, summarization_ko


RIVER_SENTENCES = [
    "Gov. Han proposed a river trial.",
    "The trial would cost $29 million.",
    "The council has not approved the trial.",
    "Residents can comment until Friday.",
    "The city will review objections next week.",
    "No construction has started.",
]


def test_english_normal_demo_keeps_governor_sentence_intact():
    output = summarization.generate_demo(
        " ".join(RIVER_SENTENCES),
        {"length": "short", "extractiveness": "normal"},
    )

    assert output == (
        "Summary: Gov. Han proposed a river trial.\n\n"
        "The trial would cost $29 million."
    )


@pytest.mark.parametrize("length,count", [("short", 2), ("normal", 4), ("long", 6)])
def test_english_fully_demo_limits_complete_source_sentences(length, count):
    output = summarization.generate_demo(
        " \n ".join(RIVER_SENTENCES),
        {"length": length, "extractiveness": "fully"},
    )

    assert output.split("\n\n") == RIVER_SENTENCES[:count]


def test_english_high_demo_numbers_complete_source_sentences():
    output = summarization.generate_demo(
        " ".join(RIVER_SENTENCES),
        {"length": "short", "extractiveness": "high"},
    )

    assert output == (
        "Key point 1: Gov. Han proposed a river trial.\n\n"
        "Key point 2: The trial would cost $29 million."
    )


@pytest.mark.parametrize("demo,separator", [
    (summarization, "\n\n"),
    (summarization_ko, " "),
])
@pytest.mark.parametrize("first,second", [
    ("Rep. J. Smith asked for a review.", "The decision is pending."),
    ("Dr. Lin visited the U.S. State Department.", "The meeting ended."),
    ("E! News reported the delay.", "The date is unknown."),
    ("The agency works in the U.S.", "The budget is unchanged."),
    ("She addressed the Gov.", "Then the hearing ended."),
    ("The show airs on E!", "The date is unknown."),
])
def test_demo_preserves_abbreviations_and_real_sentence_boundaries(demo, separator, first, second):
    output = demo.generate_demo(
        f"{first}\n\t{second} A later sentence is outside the short summary.",
        {"length": "short", "extractiveness": "fully"},
    )

    assert output == separator.join([first, second])


@pytest.mark.parametrize("source", ["", " \n\t "])
@pytest.mark.parametrize("demo,mode,expected", [
    (summarization, "normal", "Summary: No source text was provided."),
    (summarization, "high", "Key point 1: No source text was provided."),
    (summarization, "fully", "No source text was provided."),
    (summarization_ko, "normal", "- 원문이 입력되지 않았습니다"),
    (summarization_ko, "high", "핵심 1. 원문이 입력되지 않았습니다."),
    (summarization_ko, "fully", "원문이 입력되지 않았습니다."),
])
def test_empty_demo_source_keeps_existing_fallback(source, demo, mode, expected):
    assert demo.generate_demo(source, {"extractiveness": mode}) == expected


@pytest.mark.parametrize("mode,expected", [
    ("normal", "- Gov. Han은 시범 사업을 제안\n- 예산은 29억 원이다"),
    ("high", "핵심 1. Gov. Han은 시범 사업을 제안했다.\n\n핵심 2. 예산은 29억 원이다."),
    ("fully", "Gov. Han은 시범 사업을 제안했다. 예산은 29억 원이다."),
])
def test_korean_demo_preserves_title_and_existing_output_styles(mode, expected):
    source = (
        "Gov. Han은 시범 사업을 제안했다.\n"
        "예산은 29억 원이다. 시의회는 아직 승인하지 않았다."
    )

    assert summarization_ko.generate_demo(
        source, {"length": "short", "extractiveness": mode},
    ) == expected


def test_korean_sentence_split_preserves_full_stop_and_whitespace_normalization():
    assert summarization_ko._sentences("  사업을 제안했다。\n\t예산은 29억 원이다.  ") == [
        "사업을 제안했다。",
        "예산은 29억 원이다.",
    ]
