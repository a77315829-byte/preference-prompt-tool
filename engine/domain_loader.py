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
class FinalPromptSpec:
    """사용자에게 건네는 최종 프롬프트의 틀에 들어갈 문구. 전부 YAML 에서
    온다 - 엔진은 순서대로 이어 붙이기만 한다."""

    role: str
    preference_heading: str
    rules_heading: str
    rules: list[str]
    output_heading: str
    output: str
    axis_labels: dict[str, str] = field(default_factory=dict)


@dataclass
class Domain:
    name: str
    task_description: str
    checks_module: str
    axes: list[Axis]
    # 이 도메인의 전형적인 입력 몇 개. 최적화가 사용자 원문 하나에만 맞춰
    # 그 내용을 프롬프트에 박아 넣지 않도록 평가용으로 쓴다. 선택 항목.
    example_sources: list[str] = field(default_factory=list)
    # 선택 항목. 없으면 최종 프롬프트는 후보 생성용 프롬프트와 같다.
    final_prompt: FinalPromptSpec | None = None
    # 만든 프롬프트를 내보낼 곳의 이름 목록. 선택 항목이고, 비어 있으면
    # 화면 쪽 기본값을 쓴다. 이름의 뜻은 엔진이 아니라 화면 쪽이 안다.
    export_targets: list[str] = field(default_factory=list)

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


class DomainError(ValueError):
    """도메인 정의가 엔진이 돌 수 없는 모양일 때."""


def _require(mapping: dict, key: str, where: str) -> object:
    if key not in mapping or mapping[key] in (None, ""):
        raise DomainError(f"{where}: '{key}' 가 없다")
    return mapping[key]


def _validate(raw: dict, path: Path) -> None:
    """엔진이 전제하는 모양인지 로드 시점에 확인한다.

    어기면 한참 뒤에 엉뚱한 곳에서 터진다 - 값이 하나뿐인 enum 축은 순차
    선택기를 무한 루프에 빠뜨리고, enum 축이 없으면 0으로 나누고, 중복된
    값 이름은 추정 결과를 조용히 덮어쓴다. 새 도메인은 YAML 만 써서
    붙이는 것이 목표이므로 틀린 YAML 은 여기서 이유와 함께 거부한다.
    """
    where = str(path)
    for key in ("domain", "task_description", "checks_module", "axes"):
        _require(raw, key, where)

    axis_names: set[str] = set()
    enum_count = 0
    for i, axis in enumerate(raw["axes"]):
        name = _require(axis, "name", f"{where} axes[{i}]")
        at = f"{where} 축 '{name}'"
        if name in axis_names:
            raise DomainError(f"{at}: 축 이름이 중복된다")
        axis_names.add(name)

        if _require(axis, "type", at) == "enum":
            enum_count += 1
            values = _require(axis, "values", at)
            seen: set[str] = set()
            for v in values:
                value = _require(v, "value", at)
                _require(v, "prompt", f"{at} 값 '{value}'")
                _require(_require(v, "check", f"{at} 값 '{value}'"), "fn", f"{at} 값 '{value}'")
                if value in seen:
                    raise DomainError(f"{at}: 값 '{value}' 가 중복된다")
                seen.add(value)
            if len(seen) < 2:
                raise DomainError(f"{at}: enum 축은 비교할 값이 2개 이상 있어야 한다")
        else:
            _require(axis, "prompt_template", at)
            _require(_require(axis, "check", at), "fn", at)

    if enum_count == 0:
        raise DomainError(f"{where}: 선택으로 학습할 enum 축이 하나도 없다")

    final = raw.get("final_prompt")
    if final is not None:
        at = f"{where} final_prompt"
        for key in ("role", "preference_heading", "rules_heading", "output_heading", "output"):
            if not isinstance(final.get(key), str) or not final[key].strip():
                raise DomainError(f"{at}: '{key}' 는 비어 있지 않은 문자열이어야 한다")
        rules = final.get("rules")
        if not isinstance(rules, list) or not rules or not all(isinstance(r, str) and r.strip() for r in rules):
            raise DomainError(f"{at}: 'rules' 는 비어 있지 않은 문자열 목록이어야 한다")
        unknown = set(final.get("axis_labels", {})) - axis_names
        if unknown:
            raise DomainError(f"{at}: axis_labels 에 없는 축이 있다: {sorted(unknown)}")

    targets = raw.get("export_targets", [])
    if not isinstance(targets, list) or not all(isinstance(t, str) and t.strip() for t in targets):
        raise DomainError(f"{where}: export_targets 는 비어 있지 않은 문자열 목록이어야 한다")

    examples = raw.get("example_sources", [])
    if not isinstance(examples, list) or not all(isinstance(e, str) and e.strip() for e in examples):
        raise DomainError(f"{where}: example_sources 는 비어 있지 않은 문자열 목록이어야 한다")


def load_domain(path: str | Path) -> Domain:
    raw = _read_raw(Path(path))
    _validate(raw, Path(path))

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
        example_sources=[e.strip() for e in raw.get("example_sources", [])],
        final_prompt=_final_prompt(raw.get("final_prompt")),
        export_targets=[t.strip() for t in raw.get("export_targets", [])],
    )


def _final_prompt(raw: dict | None) -> FinalPromptSpec | None:
    if raw is None:
        return None
    return FinalPromptSpec(
        role=raw["role"].strip(),
        preference_heading=raw["preference_heading"].strip(),
        rules_heading=raw["rules_heading"].strip(),
        rules=[r.strip() for r in raw["rules"]],
        output_heading=raw["output_heading"].strip(),
        output=raw["output"].strip(),
        axis_labels=dict(raw.get("axis_labels", {})),
    )
