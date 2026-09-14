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
