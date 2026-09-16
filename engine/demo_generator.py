"""도메인별 규칙 기반 데모 생성기를 불러오는 공통 라우터.

`demos.<도메인명>` 이 있으면 그것을 쓰고, 없으면 `demos.generic` 으로
내려간다. 전에는 전용 모듈이 없으면 예외를 던져서, 새 도메인을 앱에
붙이려면 데모 생성기를 손으로 써야 했다 - engine/ 은 안 고쳐도 되지만
데모는 짜야 한다는 구멍이 확장성 주장에 남아 있었다. 이제 domains/*.yaml
과 checks/*.py 만 추가하면 데모 모드까지 동작한다.

이 모듈은 축이 N개 있고 각 축에 값이 M개 있다는 것만 알 뿐, 어떤
도메인인지는 모른다 (절대 규칙 1).
"""

from __future__ import annotations

import importlib

from engine.domain_loader import Domain

FALLBACK_MODULE = "demos.generic"


def generate_demo(domain: Domain, source_text: str, combo: dict[str, str]) -> str:
    """도메인 이름으로 해당 데모 생성기를 찾아 결과를 반환한다."""
    module_name = f"demos.{domain.name}"
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        if exc.name != module_name:
            # 전용 모듈은 있는데 그 안의 import 가 실패한 경우다. 조용히
            # 기본 생성기로 내려가면 원인을 못 찾으므로 그대로 올린다.
            raise
        module = importlib.import_module(FALLBACK_MODULE)
        # 기본 생성기는 구현하지 않은 축의 지침을 화면에 적기 위해
        # 도메인 정의를 함께 받는다.
        return module.generate_demo(source_text, combo, domain=domain)
    return module.generate_demo(source_text, combo)
