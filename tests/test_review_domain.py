"""고객 리뷰 도메인 검증. engine/ 코드를 한 줄도 안 고치고 완전히 다른
과제 카테고리(요약도 코딩도 아닌 리뷰 작성)가 동작하는지 확인한다."""

from dotenv import load_dotenv

from engine.domain_loader import load_domain
from engine.estimator import Comparison, Estimator
from engine.generator import generate
from engine.metric_builder import build_metric
from engine.selector import UncertaintySelector

load_dotenv()

MODEL = "openai/gpt-4.1-mini"

NOTES = (
    "Visited a small Italian restaurant downtown last night. The pasta was "
    "genuinely delicious and the waiter recommended a great wine pairing. "
    "However we waited almost 25 minutes just to get seated even with a "
    "reservation, and the table next to us was quite noisy."
)


def main() -> None:
    domain = load_domain("domains/review.yaml")
    print("domain:", domain.name, "axes:", [a.name for a in domain.axes])

    positive_short = generate(
        domain, NOTES, {"length": "short", "sentiment": "positive", "topic": ""}, model=MODEL
    )
    negative_short = generate(
        domain, NOTES, {"length": "short", "sentiment": "negative", "topic": ""}, model=MODEL
    )

    print()
    print("[positive+short]", positive_short)
    print()
    print("[negative+short]", negative_short)

    estimator = Estimator(domain)
    selector = UncertaintySelector(domain, seed=0)
    preferred = {"length": "short", "sentiment": "positive"}

    for i in range(6):
        combo_a, combo_b = selector.next_pair(estimator)
        cand_a = generate(domain, NOTES, combo_a, model=MODEL)
        cand_b = generate(domain, NOTES, combo_b, model=MODEL)

        def match(combo: dict) -> int:
            return sum(1 for k, v in preferred.items() if combo.get(k) == v)

        winner = "a" if match(combo_a) >= match(combo_b) else "b"
        estimator.update(Comparison(combo_a, combo_b, winner))
        print(f"round {i + 1}: A={combo_a} B={combo_b} -> {winner}")

    learned = {n: estimator.preferred_value(n) for n in estimator.enum_axis_names()}
    print("learned:", learned, "(expect", preferred, ")")

    metric = build_metric(domain, estimator)
    score_pos, feedback_pos = metric(positive_short, NOTES)
    score_neg, feedback_neg = metric(negative_short, NOTES)
    print()
    print("metric(positive+short) =", round(score_pos, 3), "|", feedback_pos)
    print("metric(negative+short) =", round(score_neg, 3), "|", feedback_neg)


if __name__ == "__main__":
    main()


# --- 자동 회귀 테스트 ------------------------------------------------------

import pytest

from checks.review import sentiment as sentiment_score


def _rule_choice(preferred: dict, combo_a: dict, combo_b: dict) -> str:
    match = lambda c: sum(1 for k, v in preferred.items() if c.get(k) == v)
    return "a" if match(combo_a) >= match(combo_b) else "b"


@pytest.fixture(scope="module")
def review_domain():
    return load_domain("domains/review.yaml")


@pytest.mark.api
def test_sentiment_axis_moves_the_lexicon_score(review_domain, model) -> None:
    """어조 축이 실제로 어조를 바꾸는지. 이 축의 임계값은 Yelp 3,000건으로
    보정했으므로, 생성 결과가 그 방향을 따르지 않으면 도메인이 무의미하다."""
    positive = generate(
        review_domain, NOTES, {"length": "short", "sentiment": "positive", "topic": ""}, model=model
    )
    negative = generate(
        review_domain, NOTES, {"length": "short", "sentiment": "negative", "topic": ""}, model=model
    )
    assert positive.strip() and negative.strip()
    assert positive != negative

    pos_score, _ = sentiment_score(positive, NOTES, "positive", {"min_score": 0.02})
    neg_score, _ = sentiment_score(negative, NOTES, "negative", {"max_score": 0.007})
    assert pos_score == pytest.approx(1.0)
    assert neg_score == pytest.approx(1.0)


@pytest.mark.api
def test_selection_loop_learns_the_hidden_preference(review_domain, model) -> None:
    """engine/ 무수정으로 완전히 다른 과제 카테고리가 학습되는지."""
    hidden = {"length": "short", "sentiment": "positive"}
    estimator = Estimator(review_domain)
    selector = UncertaintySelector(review_domain, seed=0)

    for _ in range(6):
        combo_a, combo_b = selector.next_pair(estimator)
        generate(review_domain, NOTES, combo_a, model=model)
        generate(review_domain, NOTES, combo_b, model=model)
        estimator.update(Comparison(combo_a, combo_b, _rule_choice(hidden, combo_a, combo_b)))

    learned = {name: estimator.preferred_value(name) for name in estimator.enum_axis_names()}
    assert learned == hidden, learned


@pytest.mark.api
def test_metric_prefers_the_matching_candidate(review_domain, model) -> None:
    hidden = {"length": "short", "sentiment": "positive"}
    estimator = Estimator(review_domain)
    for _ in range(8):
        estimator.update(Comparison(
            {"length": "short", "sentiment": "positive", "topic": ""},
            {"length": "long", "sentiment": "negative", "topic": ""},
            "a",
        ))
    assert {n: estimator.preferred_value(n) for n in estimator.enum_axis_names()} == hidden

    metric = build_metric(review_domain, estimator)
    matching = generate(
        review_domain, NOTES, {"length": "short", "sentiment": "positive", "topic": ""}, model=model
    )
    mismatching = generate(
        review_domain, NOTES, {"length": "long", "sentiment": "negative", "topic": ""}, model=model
    )
    score_match, feedback_match = metric(matching, NOTES)
    score_mismatch, _ = metric(mismatching, NOTES)

    assert score_match > score_mismatch, (score_match, score_mismatch)
    assert feedback_match.strip()
