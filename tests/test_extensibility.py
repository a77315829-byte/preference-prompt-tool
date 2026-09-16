"""11주차 확장성 검증: domains/email.yaml + checks/email.py 만 추가해서
engine/ 코드(domain_loader, generator, estimator, selector, metric_builder)
를 한 줄도 안 고치고 완전히 다른 도메인이 동작하는지 확인한다."""

from dotenv import load_dotenv

from engine.domain_loader import load_domain
from engine.estimator import Comparison, Estimator
from engine.generator import generate
from engine.metric_builder import build_metric
from engine.selector import UncertaintySelector

load_dotenv()

MODEL = "openai/gpt-4.1-mini"

REQUEST = (
    "Context for the email: I'm a project manager writing to a client, Sarah, "
    "to let her know the shipment of her order (#4521) will be delayed by one "
    "week due to a supplier issue. We apologize and offer a 10% discount on "
    "her next order as compensation."
)


def main() -> None:
    domain = load_domain("domains/email.yaml")
    print("domain:", domain.name, "axes:", [a.name for a in domain.axes])

    estimator = Estimator(domain)
    selector = UncertaintySelector(domain, seed=0)

    # "짧고, 격식 있고, 산문으로" 쓰는 걸 선호한다고 가정하고 몇 라운드 돌린다.
    for i in range(6):
        combo_a, combo_b = selector.next_pair(estimator)
        cand_a = generate(domain, REQUEST, combo_a, model=MODEL)
        cand_b = generate(domain, REQUEST, combo_b, model=MODEL)

        # 사람 대신 규칙으로: short+formal+prose에 더 가까운 쪽을 선택 (데모용).
        preferred = {"length": "short", "formality": "formal", "structure": "prose"}

        def match(combo: dict) -> int:
            return sum(1 for k, v in preferred.items() if combo.get(k) == v)

        winner = "a" if match(combo_a) >= match(combo_b) else "b"
        estimator.update(Comparison(combo_a, combo_b, winner))
        print(f"round {i + 1}: A={combo_a} B={combo_b} -> {winner}")

    print("preferred:", {n: estimator.preferred_value(n) for n in estimator.enum_axis_names()})

    metric = build_metric(domain, estimator)
    sample = generate(
        domain, REQUEST, {"length": "short", "formality": "formal", "structure": "prose"}, model=MODEL
    )
    score, feedback = metric(sample, REQUEST)
    print()
    print("[sample email]")
    print(sample)
    print()
    print("metric score:", round(score, 3))
    print("feedback:", feedback)


if __name__ == "__main__":
    main()


# --- 자동 회귀 테스트 ------------------------------------------------------
# 이 파일이 확장성 주장의 근거로 README·CLAUDE.md 에 인용되는데, 예전에는
# assert 가 하나도 없어서 실패할 수 없는 스크립트였다.

import pytest

HIDDEN = {"length": "short", "formality": "formal", "structure": "prose"}


def _rule_choice(preferred: dict, combo_a: dict, combo_b: dict) -> str:
    match = lambda c: sum(1 for k, v in preferred.items() if c.get(k) == v)
    return "a" if match(combo_a) >= match(combo_b) else "b"


@pytest.fixture(scope="module")
def email_domain():
    return load_domain("domains/email.yaml")


def test_engine_loads_a_domain_it_has_never_seen(email_domain) -> None:
    """domain_loader 는 축이 N개 있고 값이 M개 있다는 것만 안다.
    이 검사는 API 없이 돈다."""
    assert email_domain.name == "email"
    assert [axis.name for axis in email_domain.axes] == ["length", "formality", "structure"]
    assert email_domain.checks_module == "checks.email"


@pytest.mark.api
def test_selection_loop_learns_the_hidden_preference(email_domain, model) -> None:
    estimator = Estimator(email_domain)
    selector = UncertaintySelector(email_domain, seed=0)

    for _ in range(6):
        combo_a, combo_b = selector.next_pair(estimator)
        generate(email_domain, REQUEST, combo_a, model=model)
        generate(email_domain, REQUEST, combo_b, model=model)
        estimator.update(Comparison(combo_a, combo_b, _rule_choice(HIDDEN, combo_a, combo_b)))

    learned = {name: estimator.preferred_value(name) for name in estimator.enum_axis_names()}
    assert learned == HIDDEN, learned


@pytest.mark.api
def test_metric_prefers_the_matching_candidate(email_domain, model) -> None:
    estimator = Estimator(email_domain)
    for _ in range(8):
        estimator.update(Comparison(
            {"length": "short", "formality": "formal", "structure": "prose"},
            {"length": "long", "formality": "casual", "structure": "bullets"},
            "a",
        ))
    assert {n: estimator.preferred_value(n) for n in estimator.enum_axis_names()} == HIDDEN

    metric = build_metric(email_domain, estimator)
    matching = generate(
        email_domain, REQUEST,
        {"length": "short", "formality": "formal", "structure": "prose"}, model=model,
    )
    mismatching = generate(
        email_domain, REQUEST,
        {"length": "long", "formality": "casual", "structure": "bullets"}, model=model,
    )
    score_match, _ = metric(matching, REQUEST)
    score_mismatch, _ = metric(mismatching, REQUEST)
    assert score_match > score_mismatch, (score_match, score_mismatch)
