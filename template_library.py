"""템플릿 라이브러리 (templates/library.yaml).

Streamlit 을 import 하지 않는다 (`service.py`, `exporters.py` 와 같은 층).

프롬프트를 모아 두는 공간은 이미 많다. 여기 템플릿의 차이는 "내 방식으로
바꾸기"가 붙는다는 것 하나다 - 템플릿의 도메인으로 비교를 돌리고, 결과는
템플릿 본문 + 추정한 선호 절이다 (`engine.generator.build_template_prompt`).
그래서 각 템플릿은 비교를 돌릴 도메인을 반드시 갖는다.
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
        templates.append(Template(**{key: item[key].strip() for key in _REQUIRED}))
    return templates


@lru_cache(maxsize=1)
def library() -> tuple[Template, ...]:
    return tuple(load_library())


def get(template_id: str) -> Template:
    for template in library():
        if template.id == template_id:
            return template
    raise TemplateError(f"템플릿을 찾을 수 없습니다: {template_id}")
