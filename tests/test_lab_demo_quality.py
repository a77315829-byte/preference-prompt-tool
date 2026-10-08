"""실험실 데모가 원문 중심이며 API 없이 재현 가능한지 확인한다."""

import pytest

from engine.demo_generator import generate_demo
from engine.domain_loader import load_domain
from engine.generator import build_final_prompt
from service import current_estimate, final_prompt, start_session, submit_choice


SUMMARY_SOURCE = (
    "The committee discussed a new transit plan. "
    "Dana approved 4 bus routes in March. "
    "The city will review costs next month. "
    "Alex requested a follow-up report."
)
EDIT_SOURCE = (
    "The team hasn't confirmed the launch date because two risks remain open. "
    "Dana owns the design review, and Alex owns testing. "
    "The launch plan covers the October release."
)
HYBRID_UI_SOURCE = (
    "The product team moved the release to Friday after reviewing the final accessibility checklist. "
    "Three issues remain unresolved before launch. "
    "Dana will review the design changes on Thursday. "
    "The team will publish a revised plan after that review. "
    "The support team will prepare customer notices. "
    "The next status update is scheduled for Friday afternoon."
)


def test_hybrid_demo_prioritizes_existing_details_without_instruction_notes() -> None:
    domain = load_domain("domains/summarization_hybrid.yaml")
    combo = {"length": "short", "extractiveness": "fully", "topic": "", "specificity": "high"}
    output = generate_demo(domain, SUMMARY_SOURCE, combo)

    assert "Dana approved 4 bus routes in March." in output
    assert "Alex requested a follow-up report." in output
    assert "아래" not in output
    assert output == generate_demo(domain, SUMMARY_SOURCE, combo)
    assert output != generate_demo(domain, SUMMARY_SOURCE, {**combo, "specificity": "normal"})


def test_document_edit_demo_uses_source_facts_and_varies_by_axis() -> None:
    domain = load_domain("domains/macsum_eval_agent.yaml")
    base = {"conciseness": "moderate", "formality": "neutral", "sentence_complexity": "moderate", "focus_on_entities": "general"}
    output = generate_demo(domain, EDIT_SOURCE, base)

    assert "launch date" in output
    assert "Dana owns the design review" in output
    assert "Here is a short draft" not in output
    assert "(으)로" not in output
    assert output == generate_demo(domain, EDIT_SOURCE, base)
    assert output != generate_demo(domain, EDIT_SOURCE, {**base, "conciseness": "concise"})
    assert output != generate_demo(domain, EDIT_SOURCE, {**base, "focus_on_entities": "entity-focused", "conciseness": "concise"})
    assert output != generate_demo(domain, EDIT_SOURCE, {**base, "sentence_complexity": "complex"})
    assert output != generate_demo(domain, EDIT_SOURCE, {**base, "sentence_complexity": "simple"})


def test_document_edit_formal_expands_source_contraction() -> None:
    domain = load_domain("domains/macsum_eval_agent.yaml")
    combo = {"conciseness": "detailed", "formality": "formal"}
    output = generate_demo(domain, EDIT_SOURCE, combo)

    assert "hasn't" not in output
    assert "has not" in output


def test_document_edit_prompt_uses_readable_instructions_for_each_choice() -> None:
    domain = load_domain("domains/macsum_eval_agent.yaml")
    base = {
        "conciseness": "moderate",
        "formality": "neutral",
        "sentence_complexity": "moderate",
        "focus_on_entities": "mixed",
    }
    for axis in domain.axes:
        for option in axis.values:
            prompt = build_final_prompt(domain, {**base, axis.name: option.value})
            assert option.prompt in prompt
            assert "(으)로" not in prompt
            assert "conciseness" not in prompt
            assert "sentence_complexity" not in prompt
            assert "focus_on_entities" not in prompt


def test_hybrid_ui_example_makes_length_choices_distinct() -> None:
    domain = load_domain("domains/summarization_hybrid.yaml")
    base = {"extractiveness": "fully", "topic": "", "specificity": "high"}
    outputs = [generate_demo(domain, HYBRID_UI_SOURCE, {**base, "length": length}) for length in ("short", "normal", "long")]

    assert len(set(outputs)) == 3


def test_hybrid_specific_detail_does_not_repeat_the_overview() -> None:
    domain = load_domain("domains/summarization_hybrid.yaml")
    output = generate_demo(
        domain,
        HYBRID_UI_SOURCE,
        {"length": "short", "extractiveness": "normal", "topic": "", "specificity": "high"},
    )

    overview, detail = output.split("Specific detail: ")
    assert detail.strip() in HYBRID_UI_SOURCE
    assert detail.strip() not in overview


def test_document_edit_ui_example_makes_all_axis_values_distinct() -> None:
    domain = load_domain("domains/macsum_eval_agent.yaml")
    base = {"conciseness": "concise", "formality": "informal", "sentence_complexity": "complex", "focus_on_entities": "general"}
    choices = {
        "conciseness": ("concise", "moderate", "detailed"),
        "formality": ("informal", "neutral", "formal"),
        "sentence_complexity": ("simple", "moderate", "complex"),
        "focus_on_entities": ("general", "mixed", "entity-focused"),
    }
    for axis, values in choices.items():
        outputs = [generate_demo(domain, EDIT_SOURCE, {**base, axis: value}) for value in values]
        assert len(set(outputs)) == len(values), axis


@pytest.mark.parametrize(
    ("domain_key", "source"),
    [
        ("review", "A ramen restaurant visit: rich broth, long wait, friendly staff."),
        ("email", "Ask the vendor to confirm the Q4 delivery date and share the updated invoice."),
        ("summarization_hybrid", HYBRID_UI_SOURCE),
        ("macsum_eval_agent", EDIT_SOURCE),
    ],
)
def test_lab_demo_completes_with_distinct_pairs_and_reproducible_prompt(domain_key, source) -> None:
    def run():
        state = start_session(
            source, domain_key, f"domains/{domain_key}.yaml", model="demo", demo_mode=True,
        )
        pairs = []
        while not state.done:
            pair = state.pair
            assert pair is not None
            assert pair.a.text != pair.b.text, (domain_key, state.round)
            pairs.append((pair.a.text, pair.b.text))
            state = submit_choice(state, pair.pair_id, "a")
        domain, estimator = current_estimate(state)
        language = next(iter(domain.final_prompt_translations), "ko")
        prompt = final_prompt(domain, estimator, language=language)
        assert prompt.strip()
        assert state.axes
        assert any(axis.estimate is not None for axis in state.axes)
        return pairs, prompt

    assert run() == run()
