"""저자 프로필 평가 함수와 few-shot 조립을 검사한다.

이 두 개가 지금 방법의 갈림길이다. 수치 절을 쌓는 길이 막혀서
(단어만 지시하면 문장이 쪼개지고, 길이만 지시하면 문단이 붕괴하고,
셋을 같이 주면 앞의 둘이 덜 지켜진다) 두 갈래로 우회했다 - 예시를
보여주는 길과, 목표를 평가 함수로 만들어 GEPA 에게 넘기는 길.

평가 함수가 틀리면 GEPA 가 엉뚱한 곳으로 최적화하고, 점수는 올라가는데
결과는 나빠진다. 그래서 순서(저자 본인 > 어긋난 출력)와 피드백의 방향을
고정한다.
"""

from __future__ import annotations

from agents.expert_onboarding import (
    ExpertExample,
    FEWSHOT_TASK_CHARS,
    PROFILE_KEYS,
    content_leakage,
    expert_form_metric,
    fewshot_prompt,
    profile_targets,
    topic_leakage,
)


def _author(answer: str, task: str = "question " * 100, count: int = 4) -> list[ExpertExample]:
    return [ExpertExample(output=answer, task=task) for _ in range(count)]


THREE_PARAGRAPHS = "First part here.\n\nSecond part here.\n\nThird part here."


def test_profile_targets_covers_every_scored_key() -> None:
    """점수에 쓰는 항목과 목표를 내는 항목이 어긋나면 조용히 0점이 섞인다."""
    targets = profile_targets(_author(THREE_PARAGRAPHS), "source " * 200)
    assert tuple(targets) == PROFILE_KEYS


def test_profile_targets_scale_with_the_source_only_when_ratio_wins() -> None:
    # 답변 길이가 원문을 따라가는 저자 - 압축률이 뽑힌다.
    tracking = [
        ExpertExample(output="w " * (n // 10), task="s " * n)
        for n in (500, 1000, 1500, 2000)
    ]
    small = profile_targets(tracking, "x " * 400)["words_per_answer"]
    large = profile_targets(tracking, "x " * 4000)["words_per_answer"]
    assert large > small * 5

    # 답변 길이가 일정한 저자 - 과제 길이가 목표를 흔들면 안 된다.
    steady = [
        ExpertExample(output="w " * 200, task="s " * n) for n in (30, 300, 900, 2000)
    ]
    assert (
        profile_targets(steady, "x " * 50)["words_per_answer"]
        == profile_targets(steady, "x " * 5000)["words_per_answer"]
    )


def test_metric_ranks_the_author_above_a_mismatched_output() -> None:
    author = _author(THREE_PARAGRAPHS)
    metric = expert_form_metric(author)
    source = "question " * 100

    own, _ = metric(THREE_PARAGRAPHS, source)
    too_long, _ = metric("word " * 500, source)
    too_short, _ = metric("Tiny.", source)
    assert own > too_long
    assert own > too_short


def test_metric_feedback_names_the_direction() -> None:
    """방향이 없으면 최적화기가 어느 쪽으로 고쳐야 할지 모른다."""
    metric = expert_form_metric(_author(THREE_PARAGRAPHS))
    source = "question " * 100

    _, long_feedback = metric("word " * 500, source)
    assert "too many words" in long_feedback

    _, short_feedback = metric("Tiny.", source)
    assert "too few words" in short_feedback


def test_metric_says_so_when_nothing_is_off() -> None:
    author = _author(THREE_PARAGRAPHS)
    score, feedback = expert_form_metric(author)(THREE_PARAGRAPHS, "question " * 100)
    assert "matches" in feedback
    assert score > 0.9


def test_metric_handles_a_zero_target_without_dividing_by_zero() -> None:
    """글머리 기호를 안 쓰는 저자의 목표는 정확히 0 이다."""
    author = _author(THREE_PARAGRAPHS)
    assert profile_targets(author, "q " * 100)["bullet_line_ratio"] == 0.0
    bulleted = "\n".join(["- one point here"] * 6)
    score, feedback = expert_form_metric(author)(bulleted, "q " * 100)
    assert 0.0 <= score <= 1.0
    assert "bulleted" in feedback


def test_metric_score_stays_in_range_for_wild_output() -> None:
    metric = expert_form_metric(_author(THREE_PARAGRAPHS))
    for text in ("", "x", "word " * 5000, "\n\n".join(["p"] * 50)):
        score, _ = metric(text, "q " * 100)
        assert 0.0 <= score <= 1.0, (text[:20], score)


def test_fewshot_prompt_keeps_answers_whole_and_trims_tasks() -> None:
    """답변을 자르면 전달하려는 형식(길이)이 왜곡된다. 과제는 잘라도 된다."""
    long_answer = "answer " * 300
    author = [ExpertExample(output=long_answer, task="task " * 500)]
    prompt = fewshot_prompt("Do the task.", author)
    assert long_answer.strip() in prompt
    # 과제는 상한 근처로 잘려 있어야 한다.
    question_line = [l for l in prompt.splitlines() if l.startswith("Question: ")][0]
    assert len(question_line) <= FEWSHOT_TASK_CHARS + len("Question: ") + 1


def test_fewshot_prompt_uses_the_requested_number_of_examples() -> None:
    author = [ExpertExample(output=f"Answer {i}.", task=f"Task {i}") for i in range(6)]
    prompt = fewshot_prompt("Do the task.", author, count=2)
    assert prompt.count("Question: ") == 2
    assert "Answer 2." not in prompt


def test_fewshot_prompt_falls_back_when_no_tasks_are_available() -> None:
    """과제가 없으면 예시를 만들 수 없다. 지시문만 돌려준다."""
    author = [ExpertExample(output="Just an answer.")]
    assert fewshot_prompt("Do the task.", author) == "Do the task."
    assert fewshot_prompt("Do the task.", []) == "Do the task."


def test_content_leakage_is_zero_for_a_generic_instruction() -> None:
    """형식만 말하는 프롬프트는 학습 자료와 겹칠 게 없다."""
    corpus = [
        ExpertExample(
            output="Suet is the hard fat around the kidneys of beef.",
            task="What is suet and why do British dumplings need it?",
        )
    ]
    generic = (
        "Answer the question. Write roughly 200 words in total, "
        "break it into about three paragraphs, and avoid bulleted lists."
    )
    assert content_leakage(generic, corpus) == 0.0


def test_content_leakage_catches_copied_domain_sentences() -> None:
    """GEPA 가 실제로 이렇게 했다 - suet 설명을 프롬프트에 그대로 박았다."""
    corpus = [
        ExpertExample(
            output="Suet is the hard fat around the kidneys of beef, and it melts slowly.",
            task="What is suet?",
        )
    ]
    leaky = (
        "Answer the question. Remember that suet is the hard fat around the "
        "kidneys of beef, and it melts slowly."
    )
    assert content_leakage(leaky, corpus) > 0.4


def test_content_leakage_ignores_punctuation_differences() -> None:
    """쉼표 하나 차이로 베낀 문구를 놓치면 지표가 쓸모없다."""
    corpus = [ExpertExample(output="Add the salt early, then taste again.", task="How?")]
    assert content_leakage("Add the salt early then taste again.", corpus) == 1.0


def test_content_leakage_handles_text_shorter_than_the_ngram() -> None:
    corpus = [ExpertExample(output="Some answer text here.", task="A question?")]
    assert content_leakage("Too short", corpus) == 0.0
    assert content_leakage("", corpus) == 0.0


def test_topic_leakage_is_zero_for_a_pure_form_prompt() -> None:
    """형식만 말하는 프롬프트에는 주제 어휘가 없어야 한다.

    대조군이 작으면 일반 영어 단어까지 "주제 어휘"로 잡힌다 - 실측에서
    대조군 40개로 쟀을 때 순수 형식 앵커가 0.105 로 나왔고, 1,148개로
    키우니 0.000 이 됐다. 그래서 대조군은 넉넉히 줘야 한다.
    """
    own = [
        ExpertExample(
            output="Suet is the hard fat around beef kidneys, used in dumplings.",
            task="What is suet?",
        )
    ]
    foreign = [
        ExpertExample(
            output="Write about roughly this many words in total, in a few paragraphs, "
                   "and match the form of the answer you are given.",
            task="How should I write an answer, in form and length and sentences?",
        )
    ]
    form_only = (
        "Match this form: write about 17 sentences, use roughly 356 words in total."
    )
    assert topic_leakage(form_only, own, foreign) == 0.0


def test_topic_leakage_catches_paraphrased_domain_words() -> None:
    """축자 지표로는 안 잡히는 혼입을 잡아야 한다.

    GEPA 가 실제로 그랬다 - 4-gram 겹침은 0.000 인데 프롬프트에 suet,
    dumplings 같은 단어가 들어 있었다.
    """
    own = [
        ExpertExample(
            output="Suet is the hard fat around beef kidneys, used in dumplings.",
            task="What is suet?",
        )
    ]
    foreign = [ExpertExample(output="Write clearly and at length.", task="How?")]
    paraphrased = "Keep in mind that dumplings often rely on suet for texture."
    assert content_leakage(paraphrased, own) == 0.0
    assert topic_leakage(paraphrased, own, foreign) > 0.2


def test_topic_leakage_handles_empty_inputs() -> None:
    own = [ExpertExample(output="Some answer.", task="A question?")]
    assert topic_leakage("", own, []) == 0.0
    assert topic_leakage("word", own, []) == 0.0  # 4자 미만은 세지 않는다
