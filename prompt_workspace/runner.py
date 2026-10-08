"""시험 실행과 검사 (계획서 5-C, 7절).

단계마다 멈출 수 있다.

1. 프롬프트가 지금 요구사항으로 만든 것인가 - 아니면 재생성부터.
2. 시험 입력이 변수 정의와 맞는가 (renderer.check_input) - 아니면 호출 전에 멈춤.
3. 검사 묶음이 있으면 입력 자체가 믿을 만한가 (예: 합계 불일치) - 아니면 멈춤.
4. 실제 생성 모드가 아니면 메시지 구성까지만 보여 준다 (preview).
5. 모델 호출 -> 형식 검사 -> 의미 검사 -> 필수 규칙은 '미평가'로 나열.

실행 기록에는 무엇으로 실행했는지(프롬프트 revision, 입력 지문, 모델, 캐시
여부)를 남긴다. 화면은 그 값과 지금 상태를 비교해 '이전 버전 결과'를 가른다.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from prompt_workspace import check_sets, llm
from prompt_workspace.contract import check, check_output, parse_output
from prompt_workspace.models import ProjectError, input_hash, new_id, status, validate_project
from prompt_workspace.renderer import build_messages, check_input

PROMPT_VERSION = "run-v1"


def _accept(text: str) -> bool:
    value, _ = parse_output(text)
    return isinstance(value, dict)


def _record(project: dict[str, Any], values: Any, **fields: Any) -> dict[str, Any]:
    artifact = project["artifact"]
    return {
        "id": new_id(),
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "artifact_revision": artifact["revision"],
        "requirements_revision": project["requirements_revision"],
        "input_hash": input_hash(values),
        "model": None,
        "cached": False,
        "output": None,
        "messages": None,
        "checks": [],
        "elapsed_seconds": None,
        "usage": None,
        **fields,
    }


def _rule_checks(project: dict[str, Any]) -> list[dict[str, str]]:
    return [
        check(f"규칙 {r['id']}", "not_evaluated", f"{r['text']} - 코드 검사 없음, 수동 확인", group="rules")
        for r in project["requirements"]["hard_rules"]
    ]


def run(
    project: dict[str, Any],
    values: Any,
    *,
    model: str,
    live: bool,
    before_call: Callable[[], None] | None = None,
) -> dict[str, Any]:
    """실행 기록 하나를 돌려준다. status 는 다음 중 하나:

    input_error  변수 누락·타입 오류 (모델 호출 안 함)
    needs_review 입력 값 자체가 확인이 필요함 (모델 호출 안 함)
    preview      실제 생성 모드가 아님 - 메시지 구성까지만
    ran          모델을 실행하고 검사함

    before_call 은 모델을 실제로 부르기 직전에만 불린다. 서버가 여기서 하루
    상한을 차감한다 - 입력 오류로 멈춘 시험까지 상한을 깎지 않게.
    """
    validate_project(project)
    if project.get("artifact") is None:
        raise ProjectError("먼저 프롬프트를 생성해 주세요.")
    if status(project)["stage"] != "built":
        raise ProjectError("요구사항이 바뀌었습니다. 요구사항을 다시 확인하고 프롬프트를 다시 생성해 주세요.")

    artifact = project["artifact"]
    variables = project["requirements"]["variables"]
    problems = check_input(variables, artifact["input_template"], values)
    if problems:
        return _record(project, values if isinstance(values, dict) else {}, status="input_error",
                       checks=[check(p["variable"] or "입력", "fail", p["message"], group="input") for p in problems])

    checker = check_sets.get(project.get("check_set"))
    if checker is not None:
        input_problems = checker.check_input(values)
        if input_problems:
            return _record(project, values, status="needs_review", checks=input_problems)

    messages = build_messages(artifact["system_prompt"], artifact["input_template"], values)
    contract = project["requirements"]["output_contract"]
    if not live:
        not_run = [check("모델 실행", "not_evaluated",
                         "실제 생성 모드가 아니라 실행하지 않음 (서버를 PPT_LIVE=1 로 켜면 실행)", group="contract")]
        return _record(project, values, status="preview", messages=messages, checks=not_run + _rule_checks(project))

    if before_call is not None:
        before_call()
    result = llm.call(messages[0]["content"], messages[1]["content"], model=model,
                      version=PROMPT_VERSION, accept=_accept)
    parsed, checks = check_output(contract, result["text"])
    if isinstance(parsed, dict) and checker is not None:
        checks += checker.check_output(values, parsed)
    else:
        checks.append(check("의미 정확성", "not_evaluated",
                            "이 프로젝트에는 의미 검사 묶음이 없음" if checker is None else "출력을 읽지 못해 검사 안 함",
                            group="meaning"))
    checks += _rule_checks(project)
    return _record(project, values, status="ran", model=model, cached=result["cached"],
                   output=result["text"], messages=messages, checks=checks,
                   elapsed_seconds=result["elapsed_seconds"], usage=result["usage"])


def summarize_checks(checks: list[dict[str, str]]) -> dict[str, int]:
    counts = {"pass": 0, "fail": 0, "not_evaluated": 0}
    for c in checks:
        counts[c["status"]] += 1
    return counts
