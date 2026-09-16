"""전문가 프롬프트 추출(agents/expert_onboarding.py) 검증.

가드와 통계는 API 없이 돈다. 추출 자체는 api 마커를 붙인다.
"""

import pytest

from agents.expert_onboarding import (
    ExpertAxis,
    ExpertAxisValue,
    ExpertExample,
    ExtractionReport,
    _task_description_problem,
    corpus_stats,
    extract_axes,
    to_domain,
)
from engine.generator import build_prompt


# --- 과제 서술 가드 --------------------------------------------------------
# 둘 다 실측에서 실제로 겪은 실패다. 프롬프트에 "그러지 말라"고 적는
# 것만으로는 안 막혀서 코드로 검사한다.

@pytest.mark.parametrize(
    "text",
    [
        "CNN 뉴스 기사 작성자의 스타일을 분석하라.",
        "Analyse the style of the author.",
        "Imitate the author's writing.",
        "Study the examples and describe them.",
    ],
)
def test_meta_instructions_are_rejected(text) -> None:
    """모델이 전문가의 일을 하는 대신 문체를 설명하게 되는 형태."""
    problem = _task_description_problem(text)
    assert problem and "DO the job" in problem


@pytest.mark.parametrize(
    "text",
    [
        "Summarise the given news article in English using concise sentences with minimal detail.",
        "주어진 기사를 간결한 영어로 요약하라.",
        "Write the answer in a formal tone in English.",
    ],
)
def test_style_leak_is_rejected(text) -> None:
    """문체가 과제 서술에 들어가면 축을 전부 끈 기준선이 이미 개인화된
    상태가 된다. 실측에서 expert 와 base 차이가 +0.008 로 묻혔다."""
    problem = _task_description_problem(text)
    assert problem and "belongs to the axes" in problem


@pytest.mark.parametrize(
    "text",
    [
        "Summarise the given news article in English.",
        "주어진 뉴스 기사를 영어로 요약하라.",
        "Write a code review in English for the given diff.",
    ],
)
def test_clean_task_descriptions_pass(text) -> None:
    assert _task_description_problem(text) is None


def test_too_short_is_rejected() -> None:
    assert _task_description_problem("짧다") is not None
    assert _task_description_problem("") is not None


# --- 코드로 재는 통계 ------------------------------------------------------

def test_stats_separate_short_from_long_authors() -> None:
    """LLM 에게 눈대중을 맡기지 않는 이유. 기준점이 없으면 한 사람의 글만
    보고 "무엇에 비해 긴가"를 알 수 없다. 실측에서 긴 요약을 쓰는 사람에게
    길이 축을 아예 제안하지 않았다."""
    terse = [ExpertExample(output="Rates rose. Markets reacted.", task="x " * 100)]
    verbose = [
        ExpertExample(
            output=(
                "The central bank raised its policy rate by a quarter point on Monday. "
                "Officials pointed to inflation running well above target. "
                "Analysts expect at least one further increase this year. "
                "Households with variable mortgages will feel it first."
            ),
            task="x " * 100,
        )
    ]
    short_stats = corpus_stats(terse)
    long_stats = corpus_stats(verbose)

    assert short_stats["words_per_answer"] < long_stats["words_per_answer"]
    assert short_stats["sentences_per_answer"] < long_stats["sentences_per_answer"]
    assert short_stats["answer_to_task_word_ratio"] < long_stats["answer_to_task_word_ratio"]


def test_stats_handle_missing_task() -> None:
    """task 가 없어도 축 추출은 되어야 한다. 정량 검증만 불가능하다."""
    stats = corpus_stats([ExpertExample(output="One sentence only.")])
    assert stats["sentences_per_answer"] == 1.0
    assert "answer_to_task_word_ratio" not in stats


def test_stats_on_empty_corpus_do_not_crash() -> None:
    assert corpus_stats([]) == {
        "sentences_per_answer": 0.0,
        "words_per_answer": 0.0,
        "words_per_sentence": 0.0,
    }


# --- 기존 엔진 재사용 ------------------------------------------------------

def _report() -> ExtractionReport:
    return ExtractionReport(
        task_description="Summarise the given news article in English.",
        axes=[
            ExpertAxis(
                name="detail_level",
                description="세부 정보의 양",
                author_value="minimal",
                values=[
                    ExpertAxisValue("minimal", "Keep only the essential facts."),
                    ExpertAxisValue("detailed", "Include background and context."),
                ],
            ),
            ExpertAxis(
                name="stance",
                description="주관 개입 정도",
                author_value="neutral",
                values=[
                    ExpertAxisValue("neutral", "State facts without opinion."),
                    ExpertAxisValue("opinionated", "Add your own assessment."),
                ],
            ),
        ],
    )


def test_to_domain_produces_a_domain_the_engine_can_use() -> None:
    """재사용의 접점. Domain 하나만 만들면 generator·selector·estimator 가
    수정 없이 돈다. engine/ 을 고치지 않는다는 주장의 실체다."""
    domain = to_domain(_report())
    assert [axis.name for axis in domain.axes] == ["detail_level", "stance"]
    assert all(axis.type == "enum" for axis in domain.axes)

    from engine.estimator import Estimator
    from engine.selector import UncertaintySelector

    estimator = Estimator(domain)
    assert set(estimator.enum_axis_names()) == {"detail_level", "stance"}
    combo_a, combo_b = UncertaintySelector(domain, seed=0).next_pair(estimator)
    assert combo_a != combo_b


def test_assembled_prompt_contains_task_and_chosen_instructions() -> None:
    report = _report()
    domain = to_domain(report)
    prompt = build_prompt(domain, report.author_combo())

    assert report.task_description in prompt
    assert "Keep only the essential facts." in prompt
    assert "State facts without opinion." in prompt
    # 고르지 않은 값의 지시문은 들어가면 안 된다.
    assert "Include background and context." not in prompt


def test_author_combo_reports_the_inferred_settings() -> None:
    assert _report().author_combo() == {"detail_level": "minimal", "stance": "neutral"}


def test_extraction_requires_examples() -> None:
    with pytest.raises(ValueError):
        extract_axes([])
