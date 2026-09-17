"""앱에 붙는 전문가 프로필 계층을 검사한다.

Streamlit 없이 돈다. 이 계층이 조용히 틀리면 사용자에게 잘못된 수치를
자신 있게 보여주게 되므로, 특히 **자료가 부족할 때 부족하다고 말하는지**
를 고정한다.
"""

from __future__ import annotations

from expert_profile import (
    MIN_ANSWERS,
    MIN_ANSWER_WORDS,
    RECOMMENDED_ANSWERS,
    build_anchor,
    compose_prompt,
    parse_answers,
    profile_rows,
    readiness,
)

LONG = " ".join(["word"] * 40)


def _pasted(count: int, body: str = LONG) -> str:
    return "\n\n---\n\n".join([body] * count)


def test_parses_answers_split_by_the_delimiter() -> None:
    assert len(parse_answers(_pasted(6))) == 6


def test_delimiter_tolerates_longer_hyphen_runs_and_spacing() -> None:
    """사람이 손으로 넣는 구분선이다. 하이픈 개수나 공백으로 실패하면 안 된다."""
    text = f"{LONG}\n-----\n{LONG}\n   ---   \n{LONG}"
    assert len(parse_answers(text)) == 3


def test_short_fragments_are_dropped() -> None:
    """구분선을 잘못 넣으면 빈 조각이나 한두 단어짜리 메모가 생긴다."""
    text = f"{LONG}\n---\n짧은 메모\n---\n{LONG}\n---\n\n"
    assert len(parse_answers(text)) == 2


def test_blank_lines_inside_an_answer_are_kept() -> None:
    """문단 수를 재려면 답변 안의 빈 줄이 살아 있어야 한다.

    구분선만 자르고 빈 줄은 건드리지 않는지 확인한다 - 여기서 빈 줄을
    없애면 모든 저자가 1문단으로 잡힌다.
    """
    body = f"{LONG}\n\n{LONG}\n\n{LONG}"
    parsed = parse_answers(f"{body}\n---\n{body}")
    assert len(parsed) == 2
    rows = dict(profile_rows(parsed))
    assert rows["답변당 문단"] == "3.0문단"


def test_readiness_refuses_to_report_on_too_little_material() -> None:
    level, message = readiness(MIN_ANSWERS - 1)
    assert level == "none"
    assert str(MIN_ANSWERS) in message


def test_readiness_warns_between_the_minimum_and_the_recommendation() -> None:
    """부족한데 조용히 계산해 주면 사용자가 그 수치를 믿는다."""
    level, message = readiness(MIN_ANSWERS + 1)
    assert level == "thin"
    assert str(RECOMMENDED_ANSWERS) in message


def test_readiness_is_satisfied_at_the_recommended_count() -> None:
    assert readiness(RECOMMENDED_ANSWERS)[0] == "ok"


def test_profile_shows_only_features_that_survived_the_diagnostic() -> None:
    """유보 표현·숫자·1인칭 밀도는 실제 사람 16명에서도 저자를 구분하지
    못해 기각했다. 화면에 남겨두면 없는 신호를 있다고 말하는 셈이다."""
    labels = [label for label, _ in profile_rows(parse_answers(_pasted(6)))]
    assert labels == [
        "답변당 단어", "답변당 문장", "문장당 단어", "답변당 문단", "글머리 기호 줄",
    ]


def test_anchor_is_static_when_absolute_words_win() -> None:
    """과제가 없으면 절대 단어 수가 뽑히고, 그때 앵커는 고정된다 -
    그래서 그대로 복사해 쓸 수 있는 프롬프트가 된다."""
    line, kind, per_task = build_anchor(parse_answers(_pasted(8)))
    assert kind == "absolute"
    assert per_task is False
    assert "words in total" in line


def test_anchor_states_both_words_and_sentences() -> None:
    """문장 절을 빼면 모델이 문장을 잘게 쪼갠다 (실측: 문장당 13~17단어,
    저자는 18~23). 학습 30개에서 검증한 조건이 이 두 절짜리다."""
    line, _, _ = build_anchor(parse_answers(_pasted(8)))
    assert "sentence" in line and "words" in line


def test_compose_prompt_joins_task_and_anchor() -> None:
    prompt = compose_prompt("Answer the question.", "Match this form: ...")
    assert prompt.splitlines() == ["Answer the question.", "Match this form: ..."]


def test_compose_prompt_survives_an_empty_anchor() -> None:
    assert compose_prompt("Answer the question.", "") == "Answer the question."


def test_min_answer_words_filters_by_words_not_characters() -> None:
    """한국어처럼 글자가 촘촘한 언어에서 글자 수로 재면 기준이 달라진다."""
    just_under = " ".join(["단어"] * (MIN_ANSWER_WORDS - 1))
    just_over = " ".join(["단어"] * MIN_ANSWER_WORDS)
    assert parse_answers(just_under) == []
    assert len(parse_answers(just_over)) == 1
