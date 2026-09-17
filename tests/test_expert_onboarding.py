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

from agents.expert_onboarding import (
    length_parameterization,
    RATIO_MARGIN,
    ratio_anchor,
    ratio_rule_anchor,
    stable_length_anchor,
    structure_anchor,
)


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


def test_ratio_rule_anchor_states_a_percentage_and_an_example() -> None:
    """복사해 쓸 수 있는 형태의 앵커. 백분율만 주면 모델이 어림을 크게
    틀리므로 1000단어 기준 환산치를 같이 적는다.

    다만 실측에서 이 형태는 과제별 계산에 크게 못 미쳤다 - 형식 거리
    0.016~0.073 대 0.58~0.78. 그래서 제품의 기본 경로는 과제별 계산이고,
    이건 프롬프트를 밖으로 들고 나갈 때의 차선책이다.
    """
    author = [_example(1000, 100), _example(2000, 200)]  # 압축률 10%
    rule = ratio_rule_anchor(author)

    assert "10.0%" in rule
    assert "100 words for a 1000-word source" in rule
    assert "words per sentence" in rule
    # 특정 과제에 묶이지 않아야 재사용할 수 있다.
    assert "source text" in rule


def test_ratio_rule_anchor_needs_tasks() -> None:
    assert ratio_rule_anchor([ExpertExample(output="No task here.")]) == ""
    assert ratio_rule_anchor([]) == ""


def test_length_parameterization_prefers_the_ratio_when_answers_track_the_task() -> None:
    """요약처럼 답변 길이가 원문을 따라가면 압축률이 안정적이다.

    MACSum 이 이 경우다 - 상관 0.91~0.996, 압축률 변동계수 0.08~0.10 대
    절대 단어 변동계수 0.53~0.56.
    """
    author = [
        _example(source_words=n, answer_words=n // 10)
        for n in (500, 1000, 1500, 2000, 2500)
    ]
    kind, measured = length_parameterization(author)
    assert kind == "ratio"
    assert measured["ratio_cv"] < measured["absolute_cv"]


def test_length_parameterization_prefers_absolute_words_for_qa() -> None:
    """실제 Q&A 에서는 반대다. 답변 길이는 질문의 난이도가 정한다.

    Stack Exchange 저자 4명에서 상관이 0.04~0.25 로 사라지고 압축률
    변동계수가 1.0 을 넘어 절대 단어 수(0.54~0.68)보다 불안정했다.
    이 케이스가 실패하면 3차의 결론을 다른 과제 유형에 잘못 옮기게 된다.
    """
    # 답변은 200단어 근처로 일정한데 질문 길이는 크게 흔들린다.
    author = [
        _example(source_words=n, answer_words=200)
        for n in (30, 90, 300, 800, 1500)
    ]
    kind, measured = length_parameterization(author)
    assert kind == "absolute"
    assert measured["absolute_cv"] < measured["ratio_cv"]


def test_length_parameterization_falls_back_without_tasks() -> None:
    """과제가 없으면 압축률을 잴 수 없다. 절대 단어 수로 간다."""
    author = [ExpertExample(output=" ".join(["w"] * n)) for n in (100, 150, 200)]
    kind, measured = length_parameterization(author)
    assert kind == "absolute"
    assert "ratio_cv" not in measured


def test_length_parameterization_needs_every_task_to_compare() -> None:
    """일부만 과제가 있으면 두 변동계수가 다른 표본에서 나와 비교가 안 된다."""
    author = [
        _example(source_words=1000, answer_words=100),
        ExpertExample(output=" ".join(["w"] * 150)),
        _example(source_words=2000, answer_words=200),
    ]
    kind, measured = length_parameterization(author)
    assert kind == "absolute"
    assert "ratio_cv" not in measured


def test_stable_length_anchor_scales_with_the_source_when_ratio_wins() -> None:
    author = [
        _example(source_words=n, answer_words=n // 10)
        for n in (500, 1000, 1500, 2000)
    ]
    short_line, kind, _ = stable_length_anchor(author, " ".join(["x"] * 400))
    long_line, _, _ = stable_length_anchor(author, " ".join(["x"] * 4000))
    assert kind == "ratio"
    assert "40 words" in short_line
    assert "400 words" in long_line


def test_stable_length_anchor_ignores_the_source_when_absolute_wins() -> None:
    """절대 단어 수를 골랐으면 과제 길이가 목표를 흔들어서는 안 된다."""
    author = [_example(source_words=n, answer_words=200) for n in (30, 90, 300, 800, 1500)]
    short_line, kind, _ = stable_length_anchor(author, " ".join(["x"] * 50))
    long_line, _, _ = stable_length_anchor(author, " ".join(["x"] * 5000))
    assert kind == "absolute"
    assert short_line == long_line
    assert "200 words" in short_line


def test_stable_length_anchor_always_states_a_sentence_target() -> None:
    """문장 절을 빼면 모델이 문장을 잘게 쪼갠다 (실측: 문장당 13~17단어,
    저자는 18~23, 형식 거리 3~11배 악화). 두 모수화 모두에서 붙어야 한다."""
    ratio_author = [_example(source_words=n, answer_words=n // 10) for n in (500, 1000, 1500)]
    abs_author = [_example(source_words=n, answer_words=200) for n in (30, 300, 1500)]
    for author in (ratio_author, abs_author):
        line, _, _ = stable_length_anchor(author, " ".join(["x"] * 1000))
        assert "sentence" in line


def test_stable_length_anchor_is_empty_without_usable_examples() -> None:
    assert stable_length_anchor([], "some source")[0] == ""


def test_ratio_needs_a_clear_margin_not_a_narrow_win() -> None:
    """근소한 우위로 압축률을 고르면 안 된다.

    실제 저자 u67 이 이 경우였다 - 전체 96쌍으로는 절대 쪽이 맞는데
    (절대 CV 0.511 대 압축률 0.961) 어떤 12개 분할에서 뒤집혀 압축률을
    골랐고, 형식 거리가 base 의 0.189 에서 0.797 로 아무것도 안 한 것보다
    나빠졌다. 그래서 절대 단어 수를 기본값으로 두고 마진을 건다.
    """
    # 압축률이 조금 낮지만(비율 0.95) RATIO_MARGIN 을 넘지 못하는 구성.
    author = [
        _example(source_words=s, answer_words=a)
        for s, a in ((400, 60), (900, 60), (1400, 100), (2000, 150))
    ]
    kind, measured = length_parameterization(author)
    ratio_over_absolute = measured["ratio_cv"] / measured["absolute_cv"]
    assert RATIO_MARGIN < ratio_over_absolute < 1.0, ratio_over_absolute
    assert kind == "absolute"


def test_ratio_margin_sits_in_the_measured_gap() -> None:
    """임계값이 실측한 틈 안에 있어야 한다.

    저자 11명 x 20개 분할 = 220 케이스에서 압축률CV/절대CV 비율이 요약
    쪽은 최대 0.545, Q&A 쪽은 최소 0.694 였다. 이 사이를 벗어나면 한쪽을
    체계적으로 틀린다 - 마진 1.0 에서는 13개, 0.2 에서는 15개를 틀렸다.
    """
    assert 0.545 < RATIO_MARGIN < 0.694


def test_ratio_is_still_chosen_when_it_is_clearly_steadier() -> None:
    """마진을 걸어도 요약 쪽은 그대로 압축률을 골라야 한다.

    MACSum 실측 비율은 0.05~0.545 로 임계값 아래에 확실히 들어간다.
    """
    author = [
        _example(source_words=n, answer_words=n // 10)
        for n in (500, 900, 1300, 1700, 2100)
    ]
    kind, measured = length_parameterization(author)
    assert kind == "ratio"
    assert measured["ratio_cv"] < measured["absolute_cv"] * RATIO_MARGIN


def test_perfectly_consistent_author_does_not_divide_by_zero() -> None:
    """절대 단어 수가 완벽히 일정하면 변동계수가 0 이다. 그걸로 나누면 터진다."""
    author = [_example(source_words=n, answer_words=200) for n in (30, 300, 1500)]
    kind, measured = length_parameterization(author)
    assert kind == "absolute"
    assert measured["absolute_cv"] == 0.0


def test_structure_anchor_adds_only_what_differs_from_the_model_default() -> None:
    """모델 기본값과 비슷한 항목은 붙이지 않는다.

    왜: 문단 목표를 항상 붙이면 문단 오차는 1.90 → 0.88 로 좋아지지만
    길이·문장 형식 거리가 0.158 → 0.256 으로 나빠졌다 - base(0.233)보다도
    나쁘다. 지시를 더할수록 앞의 것이 덜 지켜지므로 이득이 있을 때만 더한다.
    """
    author = [
        ExpertExample(output="One block.\n\nTwo block.\n\nThree block.", task="q " * 100)
        for _ in range(3)
    ]
    # 기본값도 3문단이면 문단 절은 붙을 이유가 없다.
    same = [
        ExpertExample(output="A here.\n\nB here.\n\nC here.", task="q " * 100)
        for _ in range(3)
    ]
    _, selected = structure_anchor(author, same, "q " * 100)
    assert "paragraphs_per_answer" not in selected

    # 기본값이 1문단이면 붙어야 한다.
    flat = [ExpertExample(output="All one block here.", task="q " * 100) for _ in range(3)]
    line, selected = structure_anchor(author, flat, "q " * 100)
    assert "paragraphs_per_answer" in selected
    assert "paragraphs" in line


def test_structure_anchor_always_keeps_the_length_clause() -> None:
    """구조 항목이 하나도 안 골려도 길이 앵커는 남아야 한다."""
    author = [ExpertExample(output="Same shape.", task="q " * 100) for _ in range(3)]
    line, selected = structure_anchor(author, list(author), "q " * 100)
    assert selected == []
    assert "words in total" in line
