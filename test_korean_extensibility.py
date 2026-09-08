"""한국어 이식성 검증 (CLAUDE.md v2, 우선순위 2). domains/summarization_ko.yaml
+ checks/summarization_ko.py 만 추가해서 engine/ 코드를 한 줄도 안 고치고
한국어 도메인이 동작하는지 확인한다.

MACSum 같은 한국어 답안지가 없으므로 정량 복원율은 내지 않는다 (절대
규칙 8). 파이프라인 완주 여부와 축별 검사 함수의 스팟 체크만 한다."""

from dotenv import load_dotenv

from engine.domain_loader import load_domain
from engine.estimator import Comparison, Estimator
from engine.generator import generate
from engine.metric_builder import build_metric
from engine.selector import UncertaintySelector

load_dotenv()

MODEL = "openai/gpt-4.1-mini"

SOURCE = (
    "서울시는 다음 달부터 시내버스 요금을 300원 인상한다고 밝혔다. "
    "시 관계자는 유가 상승과 인건비 부담으로 인상이 불가피했다고 설명했다. "
    "다만 저소득층과 청소년에게는 별도의 할인 혜택을 유지하기로 했다. "
    "시민단체는 갑작스러운 인상에 반발하며 공청회를 요구하고 나섰다. "
    "서울시는 이달 말까지 시민 의견을 수렴한 뒤 최종안을 확정할 계획이다."
)


def main() -> None:
    domain = load_domain("domains/summarization_ko.yaml")
    print("domain:", domain.name, "axes:", [a.name for a in domain.axes])

    # 파이프라인 완주: 선택 루프 (규칙 기반 대행 - 한국어 답안지가 없어 페르소나
    # 오라클 대신 "짧고 원문 그대로"를 선호한다고 가정한 대행을 쓴다).
    estimator = Estimator(domain)
    selector = UncertaintySelector(domain, seed=0)
    preferred = {"length": "short", "extractiveness": "fully"}

    for i in range(6):
        combo_a, combo_b = selector.next_pair(estimator)
        candidate_a = generate(domain, SOURCE, combo_a, model=MODEL)
        candidate_b = generate(domain, SOURCE, combo_b, model=MODEL)

        def match(combo: dict) -> int:
            return sum(1 for k, v in preferred.items() if combo.get(k) == v)

        winner = "a" if match(combo_a) >= match(combo_b) else "b"
        estimator.update(Comparison(combo_a, combo_b, winner))
        print(f"round {i + 1}: A={combo_a} B={combo_b} -> {winner}")

    learned = {n: estimator.preferred_value(n) for n in estimator.enum_axis_names()}
    print("learned:", learned, "(expect", preferred, ")")

    # 축별 검사 함수 스팟 체크: 축값이 다른 두 후보를 만들어 점수·피드백을 눈으로 확인.
    short_fully = generate(domain, SOURCE, {"length": "short", "extractiveness": "fully", "topic": ""}, model=MODEL)
    long_normal = generate(domain, SOURCE, {"length": "long", "extractiveness": "normal", "topic": ""}, model=MODEL)

    print()
    print("[short+fully]", short_fully)
    print("[long+normal]", long_normal)

    metric = build_metric(domain, estimator)
    score_short_fully, feedback_short_fully = metric(short_fully, SOURCE)
    score_long_normal, feedback_long_normal = metric(long_normal, SOURCE)

    print()
    print("metric(short+fully) =", round(score_short_fully, 3), "|", feedback_short_fully)
    print("metric(long+normal) =", round(score_long_normal, 3), "|", feedback_long_normal)


if __name__ == "__main__":
    main()
