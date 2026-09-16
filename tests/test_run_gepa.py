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


# --- 자동 회귀 테스트 ------------------------------------------------------

import pytest

PREFERENCE = {"length": "short", "extractiveness": "fully"}


def _trained_estimator(domain, rounds: int = 20):
    estimator = Estimator(domain)
    for _ in range(rounds):
        estimator.update(
            Comparison(
                {"length": "short", "extractiveness": "fully", "topic": ""},
                {"length": "long", "extractiveness": "normal", "topic": ""},
                "a",
            )
        )
    return estimator


def test_seed_prompt_carries_the_learned_preference() -> None:
    """추정된 선호가 프롬프트 문구로 옮겨지는지. API 없이 돈다.

    이 조립이 깨지면 GEPA 는 엉뚱한 시작점에서 출발하고, 사용자가 받는
    최종 산출물도 자기 선택과 무관해진다.
    """
    domain = load_domain("domains/summarization.yaml")
    estimator = _trained_estimator(domain)
    assert {n: estimator.preferred_value(n) for n in estimator.enum_axis_names()} == PREFERENCE

    seed = build_seed_prompt(domain, estimator)
    assert domain.task_description.strip() in seed
    # 선호한 축값의 지시문이 들어 있어야 한다.
    assert domain.axis("length").instruction_for("short") in seed
    assert domain.axis("extractiveness").instruction_for("fully") in seed
    # 고르지 않은 값의 지시문은 없어야 한다.
    assert domain.axis("length").instruction_for("long") not in seed


def test_topic_axis_is_inactive_by_default() -> None:
    """자유 키워드 축은 값이 비면 프롬프트에 끼어들지 않아야 한다."""
    domain = load_domain("domains/summarization.yaml")
    seed = build_seed_prompt(domain, _trained_estimator(domain))
    assert "초점" not in seed and "focus on" not in seed.lower()

    with_topic = build_seed_prompt(domain, _trained_estimator(domain), topic="housing")
    assert "housing" in with_topic


@pytest.mark.api
@pytest.mark.macsum
def test_optimize_returns_a_usable_prompt(macsum_source) -> None:
    """run() 이 GEPA 를 거쳐 쓸 수 있는 프롬프트를 돌려주는지.

    gepa 0.1.4 는 metric= 인자를 받지 않아 DefaultAdapter 로 감싸야 했다.
    그 배선이 깨지면 여기서 잡힌다. 호출 예산은 작게 잡는다.
    """
    domain = load_domain("domains/summarization.yaml")
    estimator = _trained_estimator(domain)

    optimized, result = run(
        domain,
        estimator,
        train_sources=[macsum_source],
        val_sources=[macsum_source],
        max_metric_calls=4,
    )
    assert isinstance(optimized, str)
    assert optimized.strip()
    assert "system_prompt" in result.best_candidate
