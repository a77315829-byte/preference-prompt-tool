"""7주차 검증용: estimator(가상 선호) -> seed 프롬프트 -> metric_builder ->
run_gepa 엔드투엔드 1회 관통. 비용 관리를 위해 trainset/valset과
max_metric_calls을 작게 잡는다."""

import json
from pathlib import Path

from dotenv import load_dotenv

from engine.domain_loader import load_domain
from engine.estimator import Comparison, Estimator
from optimize.run_gepa import build_seed_prompt, run

load_dotenv()


def main() -> None:
    domain = load_domain("domains/summarization.yaml")

    # "짧고, 원문 표현을 그대로 쓰는 요약"을 선호한다고 학습시킨다 (6주차와 동일).
    estimator = Estimator(domain)
    for _ in range(20):
        estimator.update(
            Comparison(
                {"length": "short", "extractiveness": "fully", "topic": ""},
                {"length": "long", "extractiveness": "normal", "topic": ""},
                "a",
            )
        )

    seed_prompt = build_seed_prompt(domain, estimator)
    print("[seed prompt]")
    print(seed_prompt)
    print()

    records = json.loads(Path("data/macsum/dataset/macdoc/val.json").read_text(encoding="utf-8"))
    sources = [" ".join(r["source"]) for r in records[:4]]
    train_sources, val_sources = sources[:2], sources[2:4]

    optimized_prompt, result = run(
        domain,
        estimator,
        train_sources=train_sources,
        val_sources=val_sources,
        max_metric_calls=12,
    )

    print()
    print("[optimized prompt]")
    print(optimized_prompt)


if __name__ == "__main__":
    main()
