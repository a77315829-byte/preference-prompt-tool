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
