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
    """빈 입력에서도 모든 항목이 0으로 채워져야 한다. 키가 빠지면
    형식 거리와 선별 앵커 계산이 KeyError 로 죽는다."""
    stats = corpus_stats([])
    assert set(stats) == {
        "sentences_per_answer",
        "words_per_answer",
        "words_per_sentence",
        "bullet_line_ratio",
        "paragraphs_per_answer",
        "hedges_per_100w",
        "numerals_per_100w",
        "first_person_per_100w",
    }
    assert all(value == 0.0 for value in stats.values())


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


# --- 넓힌 형식 어휘 --------------------------------------------------------
# 어블레이션에서 LLM 이 제안한 축이 세 경우 모두 형식을 악화시켰고 코드로
# 잰 수치만 작동했다. 그래서 LLM 판정을 넓히는 대신 측정 항목을 넓혔다.
# MACSum 은 길이로만 갈리는 말뭉치라 아래 항목들을 실측으로 시험할 수
# 없다. 기계 장치가 제대로 재는지는 여기서 고정한다.

from agents.expert_onboarding import (
    ANCHOR_RELATIVE_THRESHOLD,
    selective_form_anchor,
)

_BULLETED = ExpertExample(
    output="- First point here.\n- Second point here.\n- Third point here.",
    task="x " * 50,
)
_PROSE = ExpertExample(
    output="The first point is here. The second follows. The third closes it.",
    task="x " * 50,
)


def test_bullet_ratio_separates_lists_from_prose() -> None:
    assert corpus_stats([_BULLETED])["bullet_line_ratio"] == 1.0
    assert corpus_stats([_PROSE])["bullet_line_ratio"] == 0.0


def test_paragraph_count_counts_blank_line_blocks() -> None:
    one = ExpertExample(output="Single block of text here.")
    three = ExpertExample(output="First block.\n\nSecond block.\n\nThird block.")
    assert corpus_stats([one])["paragraphs_per_answer"] == 1.0
    assert corpus_stats([three])["paragraphs_per_answer"] == 3.0


def test_hedging_density_is_per_hundred_words() -> None:
    hedged = ExpertExample(
        output="This may possibly be likely, and it could perhaps seem apparently true."
    )
    blunt = ExpertExample(output="This is true, and it is wrong, and it is done now.")
    assert corpus_stats([hedged])["hedges_per_100w"] > 30
    assert corpus_stats([blunt])["hedges_per_100w"] == 0.0


def test_numeral_and_first_person_density() -> None:
    example = ExpertExample(output="I saw 3 people and we counted 12,000 items in 2026.")
    stats = corpus_stats([example])
    assert stats["numerals_per_100w"] > 0
    assert stats["first_person_per_100w"] > 0

    neutral = ExpertExample(output="The team counted the items carefully and then left.")
    neutral_stats = corpus_stats([neutral])
    assert neutral_stats["numerals_per_100w"] == 0.0
    assert neutral_stats["first_person_per_100w"] == 0.0


def test_selective_anchor_skips_dimensions_that_already_match() -> None:
    """이득은 저자가 모델 기본값에서 먼 만큼 나온다는 실측 결과를 코드로
    옮긴 부분. 이미 같은 항목까지 지시하면 지시문만 길어지고, 긴 글
    저자에서 그게 과교정으로 돌아왔다."""
    author = [_PROSE, _PROSE]
    identical_default = [_PROSE, _PROSE]
    anchor, selected = selective_form_anchor(author, identical_default)
    assert anchor == ""
    assert selected == {}


def test_selective_anchor_picks_up_a_real_difference() -> None:
    bulleted_author = [_BULLETED, _BULLETED]
    prose_default = [_PROSE, _PROSE]
    anchor, selected = selective_form_anchor(bulleted_author, prose_default)

    assert "bullet_line_ratio" in selected
    assert selected["bullet_line_ratio"] >= ANCHOR_RELATIVE_THRESHOLD
    assert "bulleted list" in anchor
    assert anchor.startswith("Match this form:")


def test_selective_anchor_handles_empty_default() -> None:
    """기준점 생성이 실패해도 터지지 않아야 한다."""
    anchor, selected = selective_form_anchor([_PROSE], [])
    assert isinstance(anchor, str)
    assert isinstance(selected, dict)


# --- 압축률 기반 앵커 ------------------------------------------------------
# 저자의 길이는 상수가 아니라 원문 길이에 비례한다. 절대 단어 수로
# 모델링하다가 학습·홀드아웃 평균이 25단어씩 어긋났고, "모델이 큰 목표에
# 미달한다"는 잘못된 결론까지 냈다. 실측에서 절대 단어 수의 변동계수는
# 0.56, 압축률은 0.08 이었다.

from agents.expert_onboarding import ratio_anchor


def _example(source_words: int, answer_words: int) -> ExpertExample:
    return ExpertExample(
        output=" ".join(["word"] * answer_words) + ".",
        task=" ".join(["src"] * source_words),
    )


def test_ratio_anchor_scales_with_the_new_source() -> None:
    """같은 저자라도 긴 원문에는 긴 답을 요구해야 한다."""
    author = [_example(1000, 100), _example(2000, 200)]  # 압축률 10%

    short_source = " ".join(["s"] * 500)
    long_source = " ".join(["s"] * 4000)

    short_anchor = ratio_anchor(author, short_source)
    long_anchor = ratio_anchor(author, long_source)

    assert "roughly 50 words" in short_anchor
    assert "roughly 400 words" in long_anchor


def test_ratio_anchor_needs_tasks() -> None:
    """task 가 없으면 압축률을 계산할 수 없으므로 빈 문자열이어야 한다.
    조용히 엉뚱한 목표를 만들면 안 된다."""
    no_task = [ExpertExample(output="Some answer without a task.")]
    assert ratio_anchor(no_task, "source text here") == ""


def test_ratio_anchor_keeps_at_least_one_sentence() -> None:
    """아주 짧은 목표에서 0문장을 요구하면 안 된다."""
    author = [_example(10000, 5)]
    anchor = ratio_anchor(author, " ".join(["s"] * 20))
    assert "about 1 sentence" in anchor or "about 1 sentences" in anchor


def test_ratio_anchor_is_empty_without_examples() -> None:
    assert ratio_anchor([], "source") == ""


def test_compression_ratio_is_more_stable_than_absolute_length() -> None:
    """이 방법을 압축률로 바꾼 근거를 고정한다. 같은 저자가 원문 길이에
    따라 다른 분량을 쓰면, 절대 단어 수는 흔들리고 압축률은 안정적이다."""
    author = [_example(1000, 100), _example(3000, 300), _example(500, 50)]
    stats = corpus_stats(author)

    words = [100, 300, 50]
    mean_words = sum(words) / len(words)
    spread = (max(words) - min(words)) / mean_words

    assert spread > 1.0, "절대 단어 수는 크게 흔들린다"
    assert stats["answer_to_task_word_ratio"] == pytest.approx(0.1, abs=0.01)
