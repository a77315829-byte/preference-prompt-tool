"""6주차 검증용: estimator(가상의 학습된 선호) -> metric_builder -> checks
엔드투엔드. 실제 API로 두 후보(선호에 맞는 것/안 맞는 것)를 생성해 metric
점수가 방향에 맞게 나오는지 확인한다."""

import json
from pathlib import Path

from dotenv import load_dotenv

from engine.domain_loader import load_domain
from engine.estimator import Comparison, Estimator
from engine.generator import generate
from engine.metric_builder import build_metric

load_dotenv()


def main() -> None:
    domain = load_domain("domains/summarization.yaml")

    # "짧고, 원문 표현을 그대로 쓰는 요약"을 선호한다고 20번 학습시킨다.
    estimator = Estimator(domain)
    for _ in range(20):
        estimator.update(
            Comparison(
                {"length": "short", "extractiveness": "fully", "topic": ""},
                {"length": "long", "extractiveness": "normal", "topic": ""},
                "a",
            )
        )

    print("preferred:", {n: estimator.preferred_value(n) for n in estimator.enum_axis_names()})
    print("confidence:", {n: round(estimator.confidence(n), 2) for n in estimator.enum_axis_names()})

    metric = build_metric(domain, estimator)

    record = json.loads(Path("data/macsum/dataset/macdoc/val.json").read_text(encoding="utf-8"))[0]
    source_text = " ".join(record["source"])

    matching = generate(
        domain, source_text,
        {"length": "short", "extractiveness": "fully", "topic": ""},
        model="openai/gpt-4.1-mini",
    )
    mismatching = generate(
        domain, source_text,
        {"length": "long", "extractiveness": "normal", "topic": ""},
        model="openai/gpt-4.1-mini",
    )

    score_match, feedback_match = metric(matching, source_text)
    score_mismatch, feedback_mismatch = metric(mismatching, source_text)

    print()
    print("[선호에 맞는 후보] score =", round(score_match, 3))
    print("feedback:", feedback_match)
    print()
    print("[선호에 안 맞는 후보] score =", round(score_mismatch, 3))
    print("feedback:", feedback_mismatch)

    assert score_match > score_mismatch, "선호에 맞는 후보가 더 높은 점수를 받아야 한다"
    print("\nOK: 선호에 맞는 후보 점수가 더 높음")


if __name__ == "__main__":
    main()
