"""API 없는 데모 생성기의 기본 동작 검증."""

from engine.demo_generator import generate_demo
from engine.domain_loader import load_domain


SOURCE = (
    "A city opened a new public library on Monday. "
    "The building includes study rooms and a digital media lab. "
    "Local residents helped select the books. "
    "Officials expect thousands of visitors this year. "
    "The project took two years to complete. "
    "Weekend workshops will begin next month."
)


def test_demo_generation_varies_by_length_and_extractiveness() -> None:
    domain = load_domain("domains/summarization.yaml")
    short = generate_demo(domain, SOURCE, {"length": "short", "extractiveness": "fully"})
    long = generate_demo(domain, SOURCE, {"length": "long", "extractiveness": "fully"})
    abstract = generate_demo(domain, SOURCE, {"length": "short", "extractiveness": "normal"})

    assert short
    assert len(long) > len(short)
    assert abstract != short
    assert "Main focus" in abstract


def test_demo_generation_is_deterministic() -> None:
    domain = load_domain("domains/summarization.yaml")
    combo = {"length": "normal", "extractiveness": "high"}

    assert generate_demo(domain, SOURCE, combo) == generate_demo(domain, SOURCE, combo)


# --- demos/generic.py fallback -------------------------------------------
# 전용 데모 생성기가 없는 도메인이 기본 생성기로 내려가 동작하는지 검증.
# 이 fallback 이 "새 도메인은 YAML만 추가하면 앱까지 붙는다"는 주장의 실체다.

import pytest

from engine.demo_generator import FALLBACK_MODULE, generate_demo as route_demo
from engine.domain_loader import load_domain

REVIEW_MEMO = (
    "Visited the new ramen place near the station. Waited forty minutes. "
    "Broth was rich but the room was loud."
)
EMAIL_REQUEST = (
    "Ask the vendor to confirm the Q4 delivery date and share the updated invoice."
)


@pytest.fixture(scope="module")
def review_domain():
    return load_domain("domains/review.yaml")


@pytest.fixture(scope="module")
def email_domain():
    return load_domain("domains/email.yaml")


def test_fallback_module_is_importable() -> None:
    import importlib

    assert importlib.import_module(FALLBACK_MODULE) is not None


def test_domain_without_own_generator_still_works(review_domain) -> None:
    """예전에는 여기서 ValueError 가 났다."""
    out = route_demo(review_domain, REVIEW_MEMO, {"length": "short", "sentiment": "positive", "topic": ""})
    assert out.strip()


def test_length_axis_changes_sentence_count(review_domain) -> None:
    lengths = {}
    for value in ("short", "normal", "long"):
        out = route_demo(review_domain, REVIEW_MEMO, {"length": value, "sentiment": "neutral", "topic": ""})
        lengths[value] = out.count(".")
    assert lengths["short"] < lengths["normal"] < lengths["long"], lengths


def test_sentiment_axis_changes_wording(review_domain) -> None:
    base = {"length": "normal", "topic": ""}
    positive = route_demo(review_domain, REVIEW_MEMO, {**base, "sentiment": "positive"})
    negative = route_demo(review_domain, REVIEW_MEMO, {**base, "sentiment": "negative"})
    assert positive != negative
    assert "excellent" in positive
    assert "disappointing" in negative


def test_structure_axis_toggles_bullets(email_domain) -> None:
    base = {"length": "normal", "formality": "casual"}
    prose = route_demo(email_domain, EMAIL_REQUEST, {**base, "structure": "prose"})
    bullets = route_demo(email_domain, EMAIL_REQUEST, {**base, "structure": "bullets"})
    assert not prose.lstrip().startswith("-")
    assert bullets.lstrip().startswith("-")


def test_formality_axis_expands_contractions(email_domain) -> None:
    base = {"length": "long", "structure": "prose"}
    casual = route_demo(email_domain, EMAIL_REQUEST, {**base, "formality": "casual"})
    formal = route_demo(email_domain, EMAIL_REQUEST, {**base, "formality": "formal"})
    assert "I've" in casual
    assert "I've" not in formal
    assert "I have" in formal


def test_email_register_is_not_review_wording(email_domain) -> None:
    """어조 축이 없는 도메인에 의견문 문체를 쓰면 이메일이 리뷰처럼 읽힌다."""
    out = route_demo(email_domain, EMAIL_REQUEST, {"length": "normal", "formality": "casual", "structure": "prose"})
    assert "the experience was" not in out


def test_freeform_axis_instruction_is_surfaced(review_domain) -> None:
    """기본 생성기가 직접 구현하지 않는 축은 적용된 지침을 화면에 적는다."""
    out = route_demo(review_domain, REVIEW_MEMO, {"length": "short", "sentiment": "neutral", "topic": "broth"})
    assert "broth" in out


def test_output_is_deterministic(review_domain) -> None:
    combo = {"length": "long", "sentiment": "negative", "topic": ""}
    assert route_demo(review_domain, REVIEW_MEMO, combo) == route_demo(review_domain, REVIEW_MEMO, combo)


def test_empty_source_does_not_crash(review_domain) -> None:
    out = route_demo(review_domain, "", {"length": "short", "sentiment": "neutral", "topic": ""})
    assert out.strip()
