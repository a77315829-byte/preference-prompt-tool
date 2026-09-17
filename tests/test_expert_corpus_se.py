"""Stack Exchange 코퍼스 수집의 HTML 변환을 검사한다.

네트워크는 건드리지 않는다. 검사 대상은 변환 하나인데, 이게 틀리면
정작 재려던 특징이 조용히 0 이 된다 - 태그를 지우는 방식으로 옮기면
글머리 기호 비율과 문단 수가 전부 사라지고, 그러면 "이 코퍼스에도
신호가 없다"는 잘못된 판정이 나온다.
"""

from __future__ import annotations

from agents.expert_onboarding import ExpertExample, corpus_stats
from experiments.expert_corpus_se import html_to_text


def test_list_items_become_bullet_lines() -> None:
    """`<li>` 가 줄 앞의 "- " 로 나와야 _style_densities 가 센다."""
    text, _ = html_to_text("<p>Try this:</p><ul><li>Salt it</li><li>Rest it</li></ul>")
    lines = [line for line in text.splitlines() if line.strip()]
    assert lines == ["Try this:", "- Salt it", "- Rest it"]

    stats = corpus_stats([ExpertExample(output=text)])
    assert stats["bullet_line_ratio"] == round(2 / 3, 3)


def test_paragraphs_are_separated_by_blank_lines() -> None:
    text, _ = html_to_text("<p>First point.</p><p>Second point.</p><p>Third.</p>")
    assert corpus_stats([ExpertExample(output=text)])["paragraphs_per_answer"] == 3.0


def test_single_paragraph_stays_single() -> None:
    """빈 줄을 흘리면 문단 수가 부풀어 저자를 잘못 구분한다."""
    text, _ = html_to_text("<p>One continuous thought, no breaks at all.</p>")
    assert corpus_stats([ExpertExample(output=text)])["paragraphs_per_answer"] == 1.0
    assert "\n\n" not in text


def test_code_blocks_are_counted_and_kept_apart() -> None:
    text, blocks = html_to_text(
        "<p>Do this:</p><pre><code>simmer 20m</code></pre><p>Then serve.</p>"
    )
    assert blocks == 1
    assert "simmer 20m" in text
    # 코드가 앞뒤 문장에 붙어버리면 문장 수가 어긋난다.
    assert corpus_stats([ExpertExample(output=text)])["paragraphs_per_answer"] == 3.0


def test_entities_are_decoded() -> None:
    text, _ = html_to_text("<p>Use &quot;low&quot; heat &amp; wait.</p>")
    assert text == 'Use "low" heat & wait.'


def test_inline_tags_do_not_split_a_sentence() -> None:
    """`<em>`·`<code>` 같은 인라인 태그는 문단을 끊지 않아야 한다."""
    text, _ = html_to_text("<p>Use <em>very</em> low <code>heat</code> here.</p>")
    assert text == "Use very low heat here."


def test_empty_body_is_safe() -> None:
    assert html_to_text("") == ("", 0)
    assert html_to_text("<p></p>") == ("", 0)
