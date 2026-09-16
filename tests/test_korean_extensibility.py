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


# --- 자동 회귀 테스트 ------------------------------------------------------
# 절대 규칙 8: 한국어에서는 정량 복원율을 산출하지 않는다(답안지가 없다).
# 그래서 여기서 검사하는 것은 파이프라인 완주, 출력 언어 고정, 검사 함수의
# 판별력이고, 사람 기준 대비 정확도는 주장하지 않는다.

import re

import pytest

import checks.summarization_ko as checks_ko

HIDDEN = {"length": "short", "extractiveness": "fully"}


def _rule_choice(preferred: dict, combo_a: dict, combo_b: dict) -> str:
    match = lambda c: sum(1 for k, v in preferred.items() if c.get(k) == v)
    return "a" if match(combo_a) >= match(combo_b) else "b"


def _hangul_ratio(text: str) -> float:
    letters = re.findall(r"[가-힣A-Za-z]", text)
    if not letters:
        return 0.0
    return sum(1 for c in letters if "가" <= c <= "힣") / len(letters)


@pytest.fixture(scope="module")
def korean_domain():
    return load_domain("domains/summarization_ko.yaml")


def test_engine_is_untouched_for_the_korean_domain(korean_domain) -> None:
    """영어 도메인과 축 구성은 같고 검사 모듈만 다르다. API 없이 돈다."""
    assert korean_domain.name == "summarization_ko"
    assert korean_domain.checks_module == "checks.summarization_ko"
    assert [axis.name for axis in korean_domain.axes] == [
        "length", "extractiveness", "topic"
    ]


def test_kiwi_backend_is_used_when_available() -> None:
    """보고된 한국어 수치는 전부 Kiwi 기준이다. 실험 환경이 조용히 문자
    n-gram fallback 으로 내려앉으면 수치의 근거가 달라진다."""
    pytest.importorskip("kiwipiepy")
    assert checks_ko.active_backend() == "kiwi"


@pytest.mark.api
def test_output_language_stays_korean(korean_domain, model) -> None:
    """8주차에 겪은 언어 혼재 버그의 회귀 검사.

    task_description 이 출력 언어를 고정하지 않으면 축조합에 따라 영어가
    섞여 나오고, 그러면 겹침 기반 검사가 전부 왜곡된다.
    """
    for combo in (
        {"length": "short", "extractiveness": "fully", "topic": ""},
        {"length": "long", "extractiveness": "normal", "topic": ""},
    ):
        output = generate(korean_domain, SOURCE, combo, model=model)
        assert _hangul_ratio(output) > 0.9, (combo, output[:120])


@pytest.mark.api
def test_checks_discriminate_extractiveness(korean_domain, model) -> None:
    """원문을 그대로 발췌한 요약과 바꿔 쓴 요약의 형태소 겹침이 갈리는지."""
    verbatim = generate(
        korean_domain, SOURCE,
        {"length": "short", "extractiveness": "fully", "topic": ""}, model=model,
    )
    reworded = generate(
        korean_domain, SOURCE,
        {"length": "long", "extractiveness": "normal", "topic": ""}, model=model,
    )
    high = checks_ko._overlap_ratio(verbatim, SOURCE)
    low = checks_ko._overlap_ratio(reworded, SOURCE)
    assert high > low, (high, low)
    assert high - low > 0.2, (high, low)


@pytest.mark.api
def test_selection_loop_completes_and_learns(korean_domain, model) -> None:
    estimator = Estimator(korean_domain)
    selector = UncertaintySelector(korean_domain, seed=0)

    for _ in range(6):
        combo_a, combo_b = selector.next_pair(estimator)
        generate(korean_domain, SOURCE, combo_a, model=model)
        generate(korean_domain, SOURCE, combo_b, model=model)
        estimator.update(Comparison(combo_a, combo_b, _rule_choice(HIDDEN, combo_a, combo_b)))

    learned = {name: estimator.preferred_value(name) for name in estimator.enum_axis_names()}
    assert learned == HIDDEN, learned

    metric = build_metric(korean_domain, estimator)
    score, feedback = metric(
        generate(korean_domain, SOURCE, {**HIDDEN, "topic": ""}, model=model), SOURCE
    )
    assert score > 0.5, (score, feedback)
    assert feedback.strip()
