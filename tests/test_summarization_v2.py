"""summarization_v2: 길이 축만 원문 대비 단어 비율로 바꾼 도메인."""

from checks.summarization_v2 import length_ratio
from engine.domain_loader import load_domain

SOURCE = " ".join(["word"] * 1000)


def test_v2_overrides_only_length_and_keeps_axis_order() -> None:
    v1 = load_domain("domains/summarization.yaml")
    v2 = load_domain("domains/summarization_v2.yaml")
    assert [a.name for a in v2.axes] == [a.name for a in v1.axes]
    assert v2.axes[0].check_for("short").fn == "length_ratio"
    for i in (1, 2):  # extractiveness, topic 은 그대로
        assert v2.axes[i] == v1.axes[i]
    assert v2.task_description == v1.task_description


def test_ratio_bands_and_feedback_give_word_targets() -> None:
    target = {"min_ratio": 0.068, "max_ratio": 0.127}
    assert length_ratio(" ".join(["a"] * 100), SOURCE, "normal", target)[0] == 1.0
    score, feedback = length_ratio(" ".join(["a"] * 30), SOURCE, "normal", target)
    assert 0 < score < 1 and "68~127단어" in feedback and "더 길게" in feedback
    score, feedback = length_ratio(" ".join(["a"] * 300), SOURCE, "short", {"max_ratio": 0.068})
    assert score == 0.0 and "68단어 이하" in feedback and "더 짧게" in feedback


def test_empty_output_does_not_pass_a_lower_bound() -> None:
    """v1 에서 빈 출력이 'N 이하' 목표를 만점으로 통과한 버그가 있었다. 하한이
    없는 short 는 v1 과 같은 성질이므로 하한이 있는 값만 확인한다."""
    assert length_ratio("", SOURCE, "normal", {"min_ratio": 0.068, "max_ratio": 0.127})[0] == 0.0
