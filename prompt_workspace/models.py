"""프로젝트 자료구조와 검증. 화면과 무관한 순수 dict 기반이다.

프로젝트는 JSON 으로 화면과 서버를 오가고 그대로 내려받기·가져오기 된다.
그래서 dataclass 대신 dict 를 쓰고, 들어올 때마다 `validate_project` 로
모양을 검사한다. 모르는 값은 조용히 고치지 않고 이유와 함께 거부한다.

출력 계약(output_contract)은 **제한된 형식**이다. JSON Schema 표준이 아니다.
지원하는 것:
- 최상위는 JSON 객체 하나.
- 필드 타입: string, number, integer, boolean, array, object.
- 필드마다 required.
- array: `item_type` (위 원시 타입 중 하나) 또는 `item_fields` (객체 배열,
  한 단계만), `min_items` / `max_items`.
- object 필드는 안쪽 모양을 검사하지 않는다 (타입만 본다).
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from typing import Any

SCHEMA_VERSION = 1

FIELD_TYPES = ("string", "number", "integer", "boolean", "array", "object")
PRIMITIVE_TYPES = ("string", "number", "integer", "boolean")
VARIABLE_TYPES = ("string", "number", "integer", "boolean", "array", "object")
ORIGINS = ("extracted", "suggested", "user")

NAME = re.compile(r"^[a-z_][a-z0-9_]{0,39}$")

# 화면과 서버가 받는 크기 상한. 업무 설명은 짧은 글을 가정한다 (대량 자료·RAG
# 는 범위 밖, 계획서 4절).
MAX_DESCRIPTION_CHARS = 6_000
MAX_ITEMS = 30
MAX_TEXT_CHARS = 1_000
MAX_PROMPT_CHARS = 12_000


class ProjectError(ValueError):
    """화면에 그대로 보여 줄 수 있는 검증 오류."""


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def empty_requirements() -> dict[str, Any]:
    return {
        "purpose": {"text": "", "origin": "user", "source_excerpt": ""},
        "variables": [],
        "hard_rules": [],
        "preferences": [],
        "output_contract": {"fields": []},
        "open_questions": [],
        "resolved_questions": [],
    }


def new_project(title: str = "", raw_description: str = "", example_output: str = "") -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "id": new_id(),
        "title": title,
        "raw_description": raw_description,
        "example_output": example_output,
        "check_set": None,
        "requirements": empty_requirements(),
        "requirements_revision": 0,
        "confirmed_requirements_revision": None,
        "artifact": None,
        "runs": [],
    }


# --- 검증 -------------------------------------------------------------------


def _text(value: Any, where: str, *, limit: int = MAX_TEXT_CHARS, allow_empty: bool = True) -> str:
    if not isinstance(value, str):
        raise ProjectError(f"{where}: 문자열이어야 합니다.")
    if not allow_empty and not value.strip():
        raise ProjectError(f"{where}: 비어 있으면 안 됩니다.")
    if len(value) > limit:
        raise ProjectError(f"{where}: {limit}자 이내여야 합니다.")
    return value


def _list(value: Any, where: str) -> list:
    if not isinstance(value, list):
        raise ProjectError(f"{where}: 목록이어야 합니다.")
    if len(value) > MAX_ITEMS:
        raise ProjectError(f"{where}: {MAX_ITEMS}개 이내여야 합니다.")
    return value


def _sourced(item: Any, where: str) -> None:
    """origin / source_excerpt 가 붙는 항목 (규칙·선호·변수·목적)."""
    if item.get("origin") not in ORIGINS:
        raise ProjectError(f"{where}.origin: {ORIGINS} 중 하나여야 합니다.")
    _text(item.get("source_excerpt", ""), f"{where}.source_excerpt")


def validate_contract_fields(fields: Any, where: str, *, nested: bool = False) -> None:
    names = set()
    for i, field in enumerate(_list(fields, where)):
        at = f"{where}[{i}]"
        if not isinstance(field, dict):
            raise ProjectError(f"{at}: 객체여야 합니다.")
        name = field.get("name")
        if not isinstance(name, str) or not NAME.match(name):
            raise ProjectError(f"{at}.name: 영문 소문자·숫자·_ 로 된 이름이어야 합니다.")
        if name in names:
            raise ProjectError(f"{at}.name: '{name}' 이 중복됩니다.")
        names.add(name)
        kind = field.get("type")
        allowed = PRIMITIVE_TYPES if nested else FIELD_TYPES
        if kind not in allowed:
            raise ProjectError(f"{at}.type: {allowed} 중 하나여야 합니다.")
        if not isinstance(field.get("required"), bool):
            raise ProjectError(f"{at}.required: true 또는 false 여야 합니다.")
        _text(field.get("description", ""), f"{at}.description")
        if kind == "array":
            item_type, item_fields = field.get("item_type"), field.get("item_fields")
            if (item_type is None) == (item_fields is None):
                raise ProjectError(f"{at}: 배열은 item_type 과 item_fields 중 하나만 정합니다.")
            if item_type is not None and item_type not in PRIMITIVE_TYPES:
                raise ProjectError(f"{at}.item_type: {PRIMITIVE_TYPES} 중 하나여야 합니다.")
            if item_fields is not None:
                validate_contract_fields(item_fields, f"{at}.item_fields", nested=True)
            for bound in ("min_items", "max_items"):
                value = field.get(bound)
                if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 0):
                    raise ProjectError(f"{at}.{bound}: 0 이상의 정수여야 합니다.")
            lo, hi = field.get("min_items"), field.get("max_items")
            if lo is not None and hi is not None and lo > hi:
                raise ProjectError(f"{at}: min_items 가 max_items 보다 큽니다.")


def validate_requirements(req: Any) -> None:
    if not isinstance(req, dict):
        raise ProjectError("requirements: 객체여야 합니다.")
    purpose = req.get("purpose")
    if not isinstance(purpose, dict):
        raise ProjectError("requirements.purpose: 객체여야 합니다.")
    _text(purpose.get("text"), "목적")
    _sourced(purpose, "목적")

    names = set()
    for i, var in enumerate(_list(req.get("variables"), "변수")):
        at = f"변수[{i}]"
        if not isinstance(var, dict) or not isinstance(var.get("name"), str) or not NAME.match(var["name"]):
            raise ProjectError(f"{at}.name: 영문 소문자·숫자·_ 로 된 이름이어야 합니다.")
        if var["name"] in names:
            raise ProjectError(f"{at}.name: '{var['name']}' 이 중복됩니다.")
        names.add(var["name"])
        if var.get("type") not in VARIABLE_TYPES:
            raise ProjectError(f"{at}.type: {VARIABLE_TYPES} 중 하나여야 합니다.")
        if not isinstance(var.get("required"), bool):
            raise ProjectError(f"{at}.required: true 또는 false 여야 합니다.")
        _text(var.get("description", ""), f"{at}.description")
        _sourced(var, at)

    for key, label in (("hard_rules", "필수 규칙"), ("preferences", "선호"), ("open_questions", "미결 사항")):
        ids = set()
        for i, item in enumerate(_list(req.get(key), label)):
            at = f"{label}[{i}]"
            if not isinstance(item, dict):
                raise ProjectError(f"{at}: 객체여야 합니다.")
            _text(item.get("id"), f"{at}.id", limit=40, allow_empty=False)
            if item["id"] in ids:
                raise ProjectError(f"{at}.id: '{item['id']}' 가 중복됩니다.")
            ids.add(item["id"])
            _text(item.get("text"), f"{at}.text", allow_empty=False)
            if key != "open_questions":
                _sourced(item, at)
            else:
                # 답을 적는 중일 수 있다. 확인을 막는 것은 질문이 아직 여기 있다는 사실이다.
                _text(item.get("answer", ""), f"{at}.answer")

    # 답을 반영해 닫은 질문. 무엇을 물었고 어떻게 답했고 어느 규칙·선호로 들어갔는지
    # 남긴다 - 나중에 다시 열었을 때 왜 그 규칙이 생겼는지 알 수 있게. 예전 프로젝트에는
    # 이 칸이 없으므로 없으면 빈 목록으로 본다.
    for i, item in enumerate(_list(req.get("resolved_questions", []), "해결된 질문")):
        at = f"해결된 질문[{i}]"
        if not isinstance(item, dict):
            raise ProjectError(f"{at}: 객체여야 합니다.")
        _text(item.get("id"), f"{at}.id", limit=40, allow_empty=False)
        _text(item.get("text"), f"{at}.text", allow_empty=False)
        _text(item.get("answer"), f"{at}.answer", allow_empty=False)
        resolved_as = item.get("resolved_as")
        if resolved_as is not None and not isinstance(resolved_as, str):
            raise ProjectError(f"{at}.resolved_as: 문자열이거나 null 이어야 합니다.")

    contract = req.get("output_contract")
    if not isinstance(contract, dict):
        raise ProjectError("출력 계약: 객체여야 합니다.")
    validate_contract_fields(contract.get("fields"), "출력 계약.fields")


def validate_project(project: Any) -> dict[str, Any]:
    """들어온 프로젝트의 모양을 검사한다. 고치지 않고 그대로 돌려준다."""
    if not isinstance(project, dict):
        raise ProjectError("project: 객체여야 합니다.")
    if project.get("schema_version") != SCHEMA_VERSION:
        raise ProjectError(
            f"지원하지 않는 프로젝트 형식입니다 (schema_version {project.get('schema_version')!r}, "
            f"지원 {SCHEMA_VERSION})."
        )
    _text(project.get("id"), "id", limit=40, allow_empty=False)
    _text(project.get("title"), "작업 이름", limit=100)
    _text(project.get("raw_description"), "업무 설명", limit=MAX_DESCRIPTION_CHARS)
    _text(project.get("example_output", ""), "결과 예시", limit=MAX_DESCRIPTION_CHARS)
    # 다시 열었을 때 이어서 시험하도록 마지막 시험 입력 글을 같이 둔다. 선택 항목.
    _text(project.get("test_input_text", ""), "시험 입력", limit=MAX_PROMPT_CHARS)
    check_set = project.get("check_set")
    if check_set is not None and not isinstance(check_set, str):
        raise ProjectError("check_set: 문자열이거나 null 이어야 합니다.")
    validate_requirements(project.get("requirements"))
    for key in ("requirements_revision",):
        if not isinstance(project.get(key), int) or project[key] < 0:
            raise ProjectError(f"{key}: 0 이상의 정수여야 합니다.")
    confirmed = project.get("confirmed_requirements_revision")
    if confirmed is not None and not isinstance(confirmed, int):
        raise ProjectError("confirmed_requirements_revision: 정수이거나 null 이어야 합니다.")
    artifact = project.get("artifact")
    if artifact is not None:
        if not isinstance(artifact, dict):
            raise ProjectError("artifact: 객체여야 합니다.")
        _text(artifact.get("system_prompt"), "시스템 지침", limit=MAX_PROMPT_CHARS)
        _text(artifact.get("input_template"), "입력 템플릿", limit=MAX_PROMPT_CHARS)
        for key in ("revision", "built_from_requirements_revision"):
            if not isinstance(artifact.get(key), int):
                raise ProjectError(f"artifact.{key}: 정수여야 합니다.")
    if not isinstance(project.get("runs"), list):
        raise ProjectError("runs: 목록이어야 합니다.")
    return project


# --- 상태 -------------------------------------------------------------------


def input_hash(values: Any) -> str:
    """시험 입력의 지문. 키 순서와 공백에 흔들리지 않게 정규화한다."""
    canonical = json.dumps(values, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def requirements_confirmed(project: dict[str, Any]) -> bool:
    return project.get("confirmed_requirements_revision") == project.get("requirements_revision")


def status(project: dict[str, Any]) -> dict[str, Any]:
    """화면에 보여 줄 단계 상태 (계획서 14절의 구분).

    - draft: 요구사항 확인 전 (미결 사항이 남았거나 확인을 안 눌렀다).
    - built: 확인한 요구사항으로 생성한 프롬프트가 지금 요구사항과 맞는다.
    - stale_artifact: 프롬프트를 만든 뒤 요구사항이 바뀌었다 - 재확인·재생성 필요.
    """
    req = project["requirements"]
    open_count = len(req.get("open_questions", []))
    confirmed = requirements_confirmed(project)
    artifact = project.get("artifact")
    if artifact is None:
        stage = "confirmed" if confirmed else "draft"
    elif artifact["built_from_requirements_revision"] != project["requirements_revision"]:
        stage = "stale_artifact"
    else:
        stage = "built"
    return {
        "stage": stage,
        "requirements_confirmed": confirmed,
        "open_questions": open_count,
        "can_confirm": open_count == 0,
    }
