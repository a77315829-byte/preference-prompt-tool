"""engine/generator.build_final_prompt 검증. API 호출은 없다.

화면에 내보내는 최종 프롬프트가 축 문구 두세 줄에서 끝나던 것을, 도메인
YAML 의 final_prompt 틀(역할·선호·지킬 것·출력 형식)로 조립하게 했다.
후보 생성용 build_prompt 와 실험용 build_seed_prompt 는 바뀌면 안 된다 -
캐시 키와 보고 수치의 재현성이 거기에 걸려 있다.
"""

from pathlib import Path

import pytest
import yaml

import service
from engine.domain_loader import DomainError, load_domain
from engine.estimator import Comparison, Estimator
from engine.generator import build_final_prompt, build_prompt
from optimize.run_gepa import build_seed_prompt

DOMAINS = sorted(Path("domains").glob("*.yaml"))


def _preferred_combo(domain) -> dict[str, str]:
    combo = {a.name: a.values[-1].value for a in domain.axes if a.type == "enum"}
    combo.update({a.name: "" for a in domain.axes if a.type != "enum"})
    return combo


@pytest.mark.parametrize("path", DOMAINS, ids=lambda p: p.stem)
def test_every_domain_has_a_complete_final_prompt(path) -> None:
    domain = load_domain(path)
    assert domain.final_prompt is not None, f"{path.stem} 에 final_prompt 가 없다"
    combo = _preferred_combo(domain)
    prompt = build_final_prompt(domain, combo)

    spec = domain.final_prompt
    assert prompt.startswith(spec.role)
    assert domain.task_description in prompt
    for rule in spec.rules:
        assert rule in prompt
    assert spec.output in prompt
    # 추정한 선호가 전부 들어가야 한다. 이게 이 프롬프트의 존재 이유다.
    for axis in domain.axes:
        instruction = axis.instruction_for(combo[axis.name])
        if instruction:
            assert instruction in prompt
    # 사람용 라벨을 쓴다. 측정 방법 메모가 붙은 축 설명이 새면 안 된다.
    assert "비율)" not in prompt


def test_final_prompt_is_richer_than_seed() -> None:
    domain = load_domain("domains/summarization.yaml")
    combo = {"length": "short", "extractiveness": "high", "topic": ""}
    assert len(build_final_prompt(domain, combo)) > 3 * len(build_prompt(domain, combo))


def test_topic_goes_into_preferences_when_given() -> None:
    domain = load_domain("domains/summarization.yaml")
    prompt = build_final_prompt(domain, {"length": "short", "extractiveness": "high", "topic": "housing"})
    assert "- 초점:" in prompt and "housing" in prompt


def test_domain_without_final_prompt_falls_back(tmp_path) -> None:
    raw = yaml.safe_load(Path("domains/summarization.yaml").read_text(encoding="utf-8"))
    raw.pop("final_prompt")
    path = tmp_path / "plain.yaml"
    path.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
    domain = load_domain(path)
    combo = {"length": "short", "extractiveness": "high", "topic": ""}
    assert build_final_prompt(domain, combo) == build_prompt(domain, combo)


def test_experiment_seed_prompt_is_unchanged() -> None:
    """비교군 D 와 피드백 어블레이션이 쓰는 형태. 바뀌면 보고 수치를 다시
    낼 수 없다."""
    domain = load_domain("domains/summarization.yaml")
    estimator = Estimator(domain)
    for _ in range(5):
        estimator.update(Comparison(
            {"length": "short", "extractiveness": "fully", "topic": ""},
            {"length": "long", "extractiveness": "normal", "topic": ""}, "a"))
    assert build_seed_prompt(domain, estimator) == build_prompt(
        domain, {"length": "short", "extractiveness": "fully", "topic": ""}
    )


def test_service_final_prompt_uses_the_rich_template() -> None:
    domain = load_domain("domains/coding.yaml")
    prompt = service.final_prompt(domain, Estimator(domain))
    assert prompt.startswith(domain.final_prompt.role)


@pytest.mark.parametrize(
    "broken, message",
    [
        ({"rules": []}, "rules"),
        ({"role": ""}, "role"),
        ({"axis_labels": {"no_such_axis": "x"}}, "axis_labels"),
    ],
)
def test_malformed_final_prompt_is_rejected(tmp_path, broken, message) -> None:
    raw = yaml.safe_load(Path("domains/summarization.yaml").read_text(encoding="utf-8"))
    raw["final_prompt"].update(broken)
    path = tmp_path / "bad.yaml"
    path.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
    with pytest.raises(DomainError, match=message):
        load_domain(path)
