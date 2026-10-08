"""미결 사항에 답하고 닫기.

답은 그 자체로 정책이 되지 않는다 - 사용자가 **어디에 반영할지 고른다**:
필수 규칙으로, 선호로, 또는 프롬프트에 넣을 필요가 없는 답으로. 모델이 답을
규칙 문장으로 바꿔 쓰지 않는다 (계획서 3절: 충돌은 임의로 해결하지 않는다).

닫은 질문은 지우지 않고 resolved_questions 에 남긴다. 다시 열었을 때 그 규칙이
왜 생겼는지(무엇을 물었고 무엇이라 답했는지) 볼 수 있게.
"""

from __future__ import annotations

import copy
from typing import Any

from prompt_workspace.models import ProjectError, validate_project

TARGETS = {"hard_rule": ("hard_rules", "R"), "preference": ("preferences", "P"), "none": None}


def _next_id(items: list[dict], prefix: str) -> str:
    used = {i["id"] for i in items}
    n = len(items) + 1
    while f"{prefix}{n}" in used:
        n += 1
    return f"{prefix}{n}"


def resolve(project: dict[str, Any], question_id: str, answer: str, target: str) -> dict[str, Any]:
    """질문 하나를 닫는다. 새 프로젝트를 돌려준다 (요구사항 revision 이 오른다)."""
    validate_project(project)
    if target not in TARGETS:
        raise ProjectError(f"반영할 곳은 {tuple(TARGETS)} 중 하나여야 합니다.")
    answer = (answer or "").strip()
    if not answer:
        raise ProjectError("답을 적어 주세요.")
    project = copy.deepcopy(project)
    req = project["requirements"]
    question = next((q for q in req["open_questions"] if q["id"] == question_id), None)
    if question is None:
        raise ProjectError(f"미결 사항 {question_id} 를 찾을 수 없습니다.")

    resolved_as = None
    if TARGETS[target] is not None:
        key, prefix = TARGETS[target]
        resolved_as = _next_id(req[key], prefix)
        req[key].append({
            "id": resolved_as,
            "text": answer[:1000],
            "origin": "user",
            # 근거는 원문이 아니라 사용자가 질문에 단 답이다.
            "source_excerpt": f"{question_id} 답",
        })

    req["open_questions"] = [q for q in req["open_questions"] if q["id"] != question_id]
    resolved = req.setdefault("resolved_questions", [])
    resolved.append({
        "id": question_id,
        "text": question["text"],
        "answer": answer[:1000],
        "resolved_as": resolved_as,
    })
    project["requirements_revision"] += 1
    return validate_project(project)
