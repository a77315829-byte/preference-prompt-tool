"""프로젝트에 붙일 수 있는 의미 검사 묶음의 **고정 등록표**.

사용자가 적은 이름으로 모듈을 import 하지 않는다 - 여기 적힌 것만 쓴다.
임의 검사 코드를 공개 경로에서 실행하지 않는다는 계획서 11·13절의 조건이고,
에이전트가 만든 코드를 검증 없이 돌리지 않는다는 절대 규칙 9 와 같은 방향이다.

자유 설명으로 만든 프로젝트는 검사 묶음이 없다 (check_set = null). 그때는
형식 검사(contract.py)만 돌고, 의미 정확성은 '미평가'로 표시한다. 업무 설명
만으로 믿을 만한 의미 검사를 자동으로 얻을 수는 없다 (계획서 11절).
"""

from __future__ import annotations

from types import ModuleType

from prompt_workspace.examples import synthetic_cost

REGISTRY: dict[str, ModuleType] = {
    synthetic_cost.NAME: synthetic_cost,
}


def get(name: str | None) -> ModuleType | None:
    if name is None:
        return None
    if name not in REGISTRY:
        raise ValueError(f"등록되지 않은 검사 묶음입니다: {name}")
    return REGISTRY[name]
