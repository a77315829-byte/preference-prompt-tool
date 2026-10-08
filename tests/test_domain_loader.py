"""engine/domain_loader.py 검증 테스트. API 호출은 없다.

새 도메인은 YAML 만 써서 붙이는 것이 확장성 주장의 실체다. 그러면 틀린
YAML 은 로드 시점에 이유와 함께 거부돼야 한다 - 예전에는 값이 하나뿐인
enum 축이 순차 선택기를 무한 루프에 빠뜨렸다.
"""

from pathlib import Path

import pytest
import yaml

from engine.domain_loader import DomainError, load_domain
from engine.estimator import Estimator
from engine.selector import SequentialAxisSelector, UncertaintySelector

DOMAINS = sorted(Path("domains").glob("*.yaml"))


@pytest.mark.parametrize("path", DOMAINS, ids=lambda p: p.stem)
def test_every_shipped_domain_loads(path) -> None:
    domain = load_domain(path)
    estimator = Estimator(domain)
    for selector_cls in (SequentialAxisSelector, UncertaintySelector):
        combo_a, combo_b = selector_cls(domain).next_pair(estimator)
        assert combo_a != combo_b


def _axis(name: str, values: list[str]) -> dict:
    return {
        "name": name,
        "type": "enum",
        "values": [{"value": v, "prompt": f"p-{v}", "check": {"fn": "f"}} for v in values],
    }


def _write(tmp_path, axes: list[dict], **overrides) -> Path:
    raw = {"domain": "d", "task_description": "t", "checks_module": "m", "axes": axes}
    raw.update(overrides)
    path = tmp_path / "d.yaml"
    path.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
    return path


def test_minimal_valid_domain(tmp_path) -> None:
    domain = load_domain(_write(tmp_path, [_axis("a", ["x", "y"])]))
    assert [v.value for v in domain.axis("a").values] == ["x", "y"]


@pytest.mark.parametrize(
    "axes, message",
    [
        ([_axis("a", ["x"])], "2개 이상"),
        ([_axis("a", ["x", "x"])], "중복"),
        ([_axis("a", ["x", "y"]), _axis("a", ["x", "y"])], "축 이름이 중복"),
        (
            [{"name": "k", "type": "freeform_keyword", "prompt_template": "{value}", "check": {"fn": "f"}}],
            "enum 축이 하나도",
        ),
        (
            [_axis("a", ["x", "y"]), {"name": "k", "type": "freeform_keyword", "check": {"fn": "f"}}],
            "prompt_template",
        ),
    ],
)
def test_malformed_domain_is_rejected(tmp_path, axes, message) -> None:
    with pytest.raises(DomainError, match=message):
        load_domain(_write(tmp_path, axes))


def test_missing_top_level_key_is_rejected(tmp_path) -> None:
    with pytest.raises(DomainError, match="checks_module"):
        load_domain(_write(tmp_path, [_axis("a", ["x", "y"])], checks_module=""))


def test_example_sources_are_optional_and_checked(tmp_path) -> None:
    assert load_domain(_write(tmp_path, [_axis("a", ["x", "y"])])).example_sources == []
    loaded = load_domain(_write(tmp_path, [_axis("a", ["x", "y"])], example_sources=["  one  ", "two"]))
    assert loaded.example_sources == ["one", "two"]
    with pytest.raises(DomainError, match="example_sources"):
        load_domain(_write(tmp_path, [_axis("a", ["x", "y"])], example_sources=["ok", ""]))
