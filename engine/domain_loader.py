"""domains/*.yaml 로드 및 검증. 이 모듈은 축이 N개 있고 각 축에 값이 M개
있다는 것만 알 뿐, 어떤 도메인인지는 모른다."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class CheckSpec:
    fn: str
    target: dict


@dataclass
class AxisValue:
    value: str
    prompt: str
    check: CheckSpec


@dataclass
class Axis:
    name: str
    type: str
    description: str
    values: list[AxisValue] = field(default_factory=list)
    prompt_template: str | None = None
    empty_means_inactive: bool = False
    check: CheckSpec | None = None

    def instruction_for(self, value: str) -> str | None:
        if self.type == "enum":
            for v in self.values:
                if v.value == value:
                    return v.prompt
            raise ValueError(f"axis '{self.name}' has no value '{value}'")
        if not value and self.empty_means_inactive:
            return None
        return self.prompt_template.format(value=value)

    def check_for(self, value: str) -> CheckSpec | None:
        if self.type == "enum":
            for v in self.values:
                if v.value == value:
                    return v.check
            raise ValueError(f"axis '{self.name}' has no value '{value}'")
        if not value and self.empty_means_inactive:
            return None
        return self.check


@dataclass
class Domain:
    name: str
    task_description: str
    checks_module: str
    axes: list[Axis]

    def axis(self, name: str) -> Axis:
        for a in self.axes:
            if a.name == name:
                return a
        raise ValueError(f"unknown axis '{name}'")


def _read_raw(path: Path) -> dict:
    """YAML을 읽고, 최상위 `extends: <상대경로>` 가 있으면 그 파일을 먼저
    읽어 병합한다 (axes는 이름 기준으로 자식이 부모를 덮어쓰거나 추가하고,
    나머지 키는 자식이 있으면 자식 값을 쓴다). 여러 도메인이 축 대부분을
    공유할 때 YAML을 통째로 복사하지 않고 차이만 적을 수 있게 하기 위함이다."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    extends = raw.pop("extends", None)
    if not extends:
        return raw

    base = _read_raw(path.parent / extends)
    axes_by_name = {a["name"]: a for a in base.get("axes", [])}
    for axis in raw.get("axes", []):
        axes_by_name[axis["name"]] = axis

    merged = {**base, **raw}
    merged["axes"] = list(axes_by_name.values())
    return merged


def load_domain(path: str | Path) -> Domain:
    raw = _read_raw(Path(path))

    axes = []
    for raw_axis in raw["axes"]:
        axis_type = raw_axis["type"]
        if axis_type == "enum":
            values = [
                AxisValue(
                    value=v["value"],
                    prompt=v["prompt"],
                    check=CheckSpec(fn=v["check"]["fn"], target=v["check"].get("target", {})),
                )
                for v in raw_axis["values"]
            ]
            axes.append(
                Axis(
                    name=raw_axis["name"],
                    type=axis_type,
                    description=raw_axis.get("description", ""),
                    values=values,
                )
            )
        else:
            check_raw = raw_axis["check"]
            axes.append(
                Axis(
                    name=raw_axis["name"],
                    type=axis_type,
                    description=raw_axis.get("description", ""),
                    prompt_template=raw_axis["prompt_template"],
                    empty_means_inactive=raw_axis.get("empty_means_inactive", False),
                    check=CheckSpec(fn=check_raw["fn"], target=check_raw.get("target", {})),
                )
            )

    return Domain(
        name=raw["domain"],
        task_description=raw["task_description"],
        checks_module=raw["checks_module"],
        axes=axes,
    )
