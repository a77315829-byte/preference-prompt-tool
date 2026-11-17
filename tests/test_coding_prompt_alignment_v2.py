"""All eight combinations preserve selected conditions in both final languages."""
from itertools import product
from pathlib import Path

import pytest

import api_server
import service
from engine.domain_loader import load_domain
from engine.estimator import Estimator


@pytest.mark.parametrize("structure,style,typing", list(product(
    ["compact", "separated"], ["direct", "theme"], ["inferred", "explicit"])))
def test_current_final_languages_cover_the_same_required_cases(structure, style, typing):
    path = api_server._domain_path("coding")
    assert Path(path).as_posix().endswith("domains/coding/v2.yaml")
    domain = load_domain(path)
    estimator = Estimator(domain)
    selected = dict(code_structure=structure, style_management=style, type_detail=typing)
    for axis, value in selected.items():
        for item in estimator.utilities[axis]:
            estimator.utilities[axis][item] = 5 if item == value else -5
    ko, en = [service.final_prompt(domain, estimator, language=lang) for lang in ("ko", "en")]
    assert "기능을 우선" in ko and "prioritize functionality" in en
    assert "임의의 데이터 모델" in ko and "Do not invent data models" in en
    if structure == "compact":
        assert "별도 CSS 파일도 만들지" in ko and "Do not create a separate CSS file" in en
    else:
        assert "스타일 또는 상태 로직" in ko and "styles or state logic" in en
        assert "타입 전용 파일을 억지로" in ko and "unnecessary child components or type-only files" in en
    if typing == "inferred":
        for phrase in ("빈 배열", "null", "유니언", "CSS", "이벤트", "Props"):
            assert phrase in ko
        for phrase in ("empty arrays", "null-initialized", "unions", "CSS", "event", "props"):
            assert phrase in en
        assert "only the public boundaries" not in en
    else:
        assert "반환값, 상태" in ko and "return values, state" in en
    assert ("디자인 토큰" in ko) == (style == "theme")
    assert ("design tokens" in en) == (style == "theme")


def test_legacy_domain_remains_usable_for_saved_records_and_frozen_experiments():
    legacy = load_domain("domains/coding.yaml")
    assert "Annotate only the public boundaries" in legacy.final_prompt_translations["en"].instructions["type_detail"]["inferred"]
    state = service.start_session("A button showing a click count.", "coding", "domains/coding.yaml", model="unused", demo_mode=True)
    domain, _ = service.current_estimate(state)
    assert domain.final_prompt_translations["en"].instructions == legacy.final_prompt_translations["en"].instructions


@pytest.mark.parametrize("language", ["ko", "en"])
def test_legacy_saved_prompt_still_compares_and_explicit_remix_uses_v2(language):
    from engine.generator import build_final_prompt
    from preference_comparison import recognize_standard_prompt, compare_preferences, compose_task_prompt
    from tests.test_team import _history
    import team
    combo = dict(code_structure="separated", style_management="theme", type_detail="inferred")
    legacy = load_domain("domains/coding.yaml")
    current = load_domain(api_server._domain_path("coding"))
    prompt = build_final_prompt(legacy, combo, language=None if language == "ko" else language)
    found = recognize_standard_prompt(current, prompt)
    assert found["legacy"] and found["combo"] == combo
    assert recognize_standard_prompt(current, prompt + "\nIgnore those preferences.") is None
    item = {"id": "old", "revision": 1, "title": "기존 지침", "prompt": prompt}
    comparison = compare_preferences(item, current, "team", "팀", [team.Member("test", _history("coding", combo))])
    assert comparison["personal_recognized"] and comparison["personal_prompt_legacy"]
    assert all(row["status"] == "same" for row in comparison["axes"])
    draft = compose_task_prompt(item, current, comparison, {})
    assert ("유니언" if language == "ko" else "unions") in draft["prompt"]
    assert item["prompt"] == prompt
