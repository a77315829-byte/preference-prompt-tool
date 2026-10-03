"""최종 프롬프트 언어 선택 (영어 기본, 한국어 선택).

후보 생성 지시문(build_prompt)은 바꾸지 않는다 - 캐시 키와 실험 결과가 그 텍스트에
묶여 있다. 언어는 사용자에게 내보내는 최종 프롬프트에만 적용된다.
"""

import re
from itertools import product

import pytest

import service
from engine.domain_loader import DomainError, load_domain
from engine.estimator import Comparison, Estimator
from engine.generator import build_final_prompt, build_prompt

APP_DOMAINS = ["coding", "summarization", "summarization_ko", "idle_tracker", "review", "email"]
HANGUL = re.compile(r"[가-힣ㄱ-ㆎ]")


def _combos(domain, topic=""):
    enum_axes = [a for a in domain.axes if a.type == "enum"]
    free = {a.name: topic for a in domain.axes if a.type != "enum"}
    for values in product(*[[v.value for v in a.values] for a in enum_axes]):
        yield {**dict(zip([a.name for a in enum_axes], values)), **free}


@pytest.mark.parametrize("name", APP_DOMAINS)
def test_english_prompts_have_no_korean_for_any_preference(name) -> None:
    domain = load_domain(f"domains/{name}.yaml")
    for combo in _combos(domain):
        for team in (False, True):
            prompt = build_final_prompt(domain, combo, team=team, language="en")
            assert not HANGUL.search(prompt), (name, combo, team, prompt)
    if any(a.type != "enum" for a in domain.axes):
        combo = next(_combos(domain, topic="pricing"))
        assert '"pricing"' in build_final_prompt(domain, combo, language="en")


@pytest.mark.parametrize("name", APP_DOMAINS)
def test_without_a_language_the_korean_prompt_is_unchanged(name) -> None:
    domain = load_domain(f"domains/{name}.yaml")
    combo = next(_combos(domain))
    prompt = build_final_prompt(domain, combo)
    assert prompt.startswith(domain.final_prompt.role)
    assert HANGUL.search(prompt)


def test_english_prompt_for_korean_summaries_still_asks_for_korean_output() -> None:
    """지시문 언어와 출력 언어가 다르면 출력이 섞였던 적이 있다 (8주차)."""
    domain = load_domain("domains/summarization_ko.yaml")
    prompt = build_final_prompt(domain, next(_combos(domain)), language="en")
    assert prompt.count("Korean") >= 2


def test_unknown_language_is_an_error_and_candidate_prompts_do_not_change() -> None:
    domain = load_domain("domains/summarization.yaml")
    combo = next(_combos(domain))
    with pytest.raises(ValueError):
        build_final_prompt(domain, combo, language="fr")
    # 후보 생성 지시문은 언어 선택과 무관하다.
    assert HANGUL.search(build_prompt(domain, combo))


@pytest.mark.parametrize("break_it, message", [
    (lambda en: en["axis_labels"].update(no_such_axis="x"), "no_such_axis"),
    (lambda en: en["instructions"].update(no_such_axis={"a": "b"}), "no_such_axis"),
    (lambda en: en.pop("task"), "task"),
])
def test_translation_is_checked_when_loading(tmp_path, break_it, message) -> None:
    import yaml
    raw = yaml.safe_load(open("domains/email.yaml", encoding="utf-8"))
    break_it(raw["final_prompt_translations"]["en"])
    path = tmp_path / "email.yaml"
    path.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
    with pytest.raises(DomainError, match=message):
        load_domain(path)


def _finished_state(domain_key: str):
    state = service.start_session("A short source text. It has two sentences.", domain_key,
                                  f"domains/{domain_key}.yaml", model="m", demo_mode=True)
    while not state.done:
        state = service.submit_choice(state, state.pair.pair_id, "a")
    return state


def test_service_offers_both_languages_with_english_first() -> None:
    state = _finished_state("coding")
    domain, estimator = service.current_estimate(state)
    assert service.prompt_languages(domain) == ["en", "ko"]
    en = service.final_prompt(domain, estimator, language="en")
    assert not HANGUL.search(en)
    exports = {e.key: e for e in service.exports_for(state, en, language="en")}
    assert not HANGUL.search(exports["copilot"].content)


def test_api_payload_carries_both_languages_and_defaults_to_english() -> None:
    import api_server
    payload = api_server._state_payload(_finished_state("summarization"))
    assert set(payload["prompts"]) == {"en", "ko"}
    assert payload["prompt_language"] == "en"
    assert payload["prompt"] == payload["prompts"]["en"]
    assert set(payload["exports_by_language"]) == {"en", "ko"}
    assert not HANGUL.search(payload["exports_by_language"]["en"][0]["content"])
