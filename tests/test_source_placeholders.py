"""원문 길이 자리표시자 `{source_words*R}` (docs/length_v2_preregistration.md 4단계).

가장 중요한 것은 첫 테스트다. 자리표시자가 없는 도메인의 프롬프트는 예전과 글자
하나까지 같아야 한다 - 캐시 키가 조립된 프롬프트 텍스트라서, 한 글자라도 바뀌면
cache/ 전체와 커밋된 실험 결과의 재현이 깨진다.
"""

from itertools import product
from pathlib import Path

import pytest

from engine import generator
from engine.domain_loader import load_domain
from engine.generator import build_prompt, fill_source_placeholders

DOMAINS = sorted(Path("domains").glob("*.yaml"))
SOURCE = " ".join(["word"] * 1000)


def _old_build_prompt(domain, combo):
    """자리표시자를 넣기 전의 build_prompt 그대로."""
    lines = [domain.task_description]
    for axis in domain.axes:
        instruction = axis.instruction_for(combo.get(axis.name, ""))
        if instruction:
            lines.append(instruction)
    return "\n".join(lines)


def _combos(domain):
    enum_axes = [a for a in domain.axes if a.type == "enum"]
    for values in product(*[[v.value for v in a.values] for a in enum_axes]):
        yield dict(zip([a.name for a in enum_axes], values))


@pytest.mark.parametrize("path", [p for p in DOMAINS if p.stem != "summarization_v3"], ids=lambda p: p.stem)
def test_domains_without_placeholders_build_the_same_prompt_as_before(path) -> None:
    domain = load_domain(path)
    for combo in _combos(domain):
        old = _old_build_prompt(domain, combo)
        assert build_prompt(domain, combo) == old
        assert build_prompt(domain, combo, source=SOURCE) == old


def test_placeholder_is_filled_from_the_source_word_count() -> None:
    assert fill_source_placeholders("약 {source_words*0.053}단어", SOURCE) == "약 53단어"
    assert fill_source_placeholders("{source_words*0.1} / {source_words*0.15}", "a b c d e f g h i j") == "1 / 2"
    assert fill_source_placeholders("자리표시자 없음", None) == "자리표시자 없음"


def test_placeholder_without_a_source_is_an_error() -> None:
    """조용히 비율 문구로 바꾸면 2단계의 실패(모델이 비율을 못 따름)를 다시 만든다."""
    with pytest.raises(ValueError, match="원문"):
        fill_source_placeholders("약 {source_words*0.053}단어", None)


def test_v3_domain_fills_length_from_the_source() -> None:
    domain = load_domain("domains/summarization_v3.yaml")
    combo = {"length": "long", "extractiveness": "normal", "topic": ""}
    prompt = build_prompt(domain, combo, source=SOURCE)
    assert "약 154단어" in prompt and "{" not in prompt
    with pytest.raises(ValueError):
        build_prompt(domain, combo)


def test_generate_passes_the_source_to_the_prompt(monkeypatch) -> None:
    seen = []
    monkeypatch.setattr(generator, "generate_with_prompt", lambda prompt, *a, **k: seen.append(prompt) or "out")
    domain = load_domain("domains/summarization_v3.yaml")
    generator.generate(domain, SOURCE, {"length": "short", "extractiveness": "normal", "topic": ""}, "m")
    assert "약 53단어" in seen[0]
