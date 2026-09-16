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


# --- 자동 회귀 테스트 ------------------------------------------------------
# 위 main() 은 실제 API + MACSum 데이터가 필요하다. 아래는 손으로 쓴
# 텍스트만 써서 API 없이 돌아가는 검사다. metric 은 (출력, 원문) 문자열을
# 받으면 순수 계산이라 이렇게 검증할 수 있다.

import pytest

from engine.metric_builder import MIN_AXIS_WEIGHT

SOURCE = (
    "The city council approved a new housing plan on Monday. "
    "Officials said the plan will add twelve thousand homes by 2030. "
    "Analysts warned that construction delays could limit the effect on prices. "
    "Residents groups criticised the small share of affordable units. "
    "The council promised a follow-up package before the end of the year."
)

# 선호(short + fully)에 맞는 후보: 원문 문장을 그대로 두 개 발췌.
MATCHING = (
    "The city council approved a new housing plan on Monday. "
    "Officials said the plan will add twelve thousand homes by 2030."
)

# 선호에 어긋나는 후보: 길고, 표현을 바꿔 씀.
MISMATCHING = (
    "Local lawmakers signed off on a fresh construction programme early this week. "
    "Roughly twelve thousand dwellings are meant to appear within the decade. "
    "Experts remain sceptical that any of this will cool the market quickly. "
    "Community advocates complain too few cheap flats are included. "
    "Another set of measures has been pledged for later this year. "
    "Observers expect further debate before anything is built."
)


def _preference_estimator(domain, rounds: int = 20) -> Estimator:
    """short + fully 를 선호한다고 학습시킨 estimator."""
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


@pytest.fixture(scope="module")
def domain():
    return load_domain("domains/summarization.yaml")


@pytest.fixture
def metric(domain):
    return build_metric(domain, _preference_estimator(domain))


def test_matching_candidate_scores_higher(metric) -> None:
    """이게 metric_builder 의 존재 이유다. 추정된 선호에 맞는 결과물이
    더 높은 점수를 받아야 GEPA가 그 방향으로 최적화된다."""
    score_match, _ = metric(MATCHING, SOURCE)
    score_mismatch, _ = metric(MISMATCHING, SOURCE)
    assert score_match > score_mismatch


def test_scores_stay_in_unit_range(metric) -> None:
    for output in (MATCHING, MISMATCHING, "", SOURCE):
        score, _ = metric(output, SOURCE)
        assert 0.0 <= score <= 1.0


def test_feedback_names_each_violated_axis(metric) -> None:
    """점수만이 아니라 축별 자연어 피드백을 준다는 것이 이 프로젝트가
    범용 최적화 도구와 다르다고 주장하는 지점이다. 위반 시 축 이름이
    피드백에 드러나야 GEPA 성찰이 쓸 수 있다."""
    _, feedback = metric(MISMATCHING, SOURCE)
    assert "길이" in feedback
    assert "추출성" in feedback
    # 목표치가 함께 나와야 무엇을 고쳐야 할지 알 수 있다.
    assert "목표" in feedback


def test_feedback_reports_satisfaction_too(metric) -> None:
    _, feedback = metric(MATCHING, SOURCE)
    assert "충족" in feedback


def test_inactive_freeform_axis_is_skipped(metric) -> None:
    """topic 은 자유 키워드 축이고 비활성(빈 값)이다. 학습 대상이 아니므로
    점수에 끼어들어 만점을 막아서는 안 된다."""
    score, feedback = metric(MATCHING, SOURCE)
    assert score == pytest.approx(1.0)
    assert "주제" not in feedback


def test_low_confidence_axis_keeps_minimum_weight(domain) -> None:
    """확신도가 0인 축도 완전히 무시되지는 않아야 한다. 무시하면 아직
    모르는 축을 프롬프트가 마음대로 위반해도 점수가 안 깎인다."""
    empty = Estimator(domain)  # 선택 이력이 없으니 확신도 0
    for name in empty.enum_axis_names():
        assert empty.confidence(name) == pytest.approx(0.0, abs=1e-9)

    metric = build_metric(domain, empty)
    # 두 축 다 위반하는 결과물은 0점 근처여야 한다 - 가중치가 0이면 1.0이 된다.
    score, _ = metric(MISMATCHING, SOURCE)
    assert score < 1.0
    assert MIN_AXIS_WEIGHT > 0


def test_metric_is_deterministic(metric) -> None:
    first = metric(MATCHING, SOURCE)
    second = metric(MATCHING, SOURCE)
    assert first == second


if __name__ == "__main__":
    main()
