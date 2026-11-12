"""템플릿 라이브러리 (templates/library.yaml).

Streamlit 을 import 하지 않는다 (`service.py`, `exporters.py` 와 같은 층).

선택 비교를 지원하는 템플릿은 본문 + 추정한 선호 절로 조립한다
(`engine.generator.build_template_prompt`). 업무 양식 초안은
personalizable=False로 두고 확인·복사·요청문 점검만 제공한다.
domain은 관련 분야를 가리키며, 그 도메인의 선택 비교 지원을 보장하지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
LIBRARY_PATH = ROOT / "templates" / "library.yaml"
_REQUIRED = ("id", "domain", "category", "title", "description", "author", "license", "prompt")


class TemplateError(ValueError):
    pass


@dataclass(frozen=True)
class Template:
    id: str
    domain: str
    category: str
    title: str
    description: str
    author: str
    license: str
    prompt: str
    personalizable: bool = True
    source_url: str = ""


def load_library(path: Path = LIBRARY_PATH) -> list[Template]:
    """읽고 검증한다. 틀린 항목은 로드 시점에 이유와 함께 거부한다."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    items = raw.get("templates")
    if not isinstance(items, list) or not items:
        raise TemplateError(f"{path}: templates 목록이 비어 있다")

    templates, seen = [], set()
    for i, item in enumerate(items):
        where = f"{path} templates[{i}]"
        for key in _REQUIRED:
            if not isinstance(item.get(key), str) or not item[key].strip():
                raise TemplateError(f"{where}: '{key}' 가 없다")
        if item["id"] in seen:
            raise TemplateError(f"{where}: id '{item['id']}' 가 중복된다")
        seen.add(item["id"])
        if not (ROOT / "domains" / f"{item['domain']}.yaml").exists():
            raise TemplateError(f"{where}: 도메인 '{item['domain']}' 이 domains/ 에 없다")
        personalizable = item.get("personalizable", True)
        source_url = item.get("source_url", "")
        if type(personalizable) is not bool or not isinstance(source_url, str) or (source_url and not source_url.startswith("https://")):
            raise TemplateError(f"{where}: 개인화 여부·출처 주소가 올바르지 않다")
        templates.append(Template(**{key: item[key].strip() for key in _REQUIRED}, personalizable=personalizable, source_url=source_url))
    return templates


@lru_cache(maxsize=1)
def library() -> tuple[Template, ...]:
    return tuple(load_library())


def get(template_id: str) -> Template:
    for template in library():
        if template.id == template_id:
            return template
    raise TemplateError(f"템플릿을 찾을 수 없습니다: {template_id}")
