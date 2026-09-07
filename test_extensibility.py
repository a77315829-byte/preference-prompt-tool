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
