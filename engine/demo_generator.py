"""도메인별 규칙 기반 데모 생성기를 불러오는 공통 라우터."""

from __future__ import annotations

import importlib

from engine.domain_loader import Domain


def generate_demo(domain: Domain, source_text: str, combo: dict[str, str]) -> str:
    """도메인 이름으로 해당 데모 생성기를 찾아 결과를 반환한다."""
    try:
        module = importlib.import_module(f"demos.{domain.name}")
    except ModuleNotFoundError as exc:
        if exc.name == f"demos.{domain.name}":
            raise ValueError(f"domain '{domain.name}' has no demo generator") from exc
        raise
    return module.generate_demo(source_text, combo)
