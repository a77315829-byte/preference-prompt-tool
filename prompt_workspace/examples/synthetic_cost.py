"""'합성 비용 데이터 보고' 샘플 (계획서 8절).

**실제 AWS 계정·요금·유휴 리소스 탐지 결과가 아니다.** 서비스 이름도 일부러
Compute / Storage 처럼 일반 이름을 쓴다. AWS 기능은 팀원 담당이라 boto3,
domains/idle_tracker.yaml, checks/idle_tracker.py 를 쓰지도 고치지도 않는다.
AWS 담당자는 이 모듈의 입력 계약(SAMPLE_INPUT 모양)과 check_input /
check_output 을 보고 자기 데이터를 연결할지 정한다.

금액은 문자열로 주고받고 Decimal 로 비교한다 - float 로 더하면 37.50 이
37.499999 가 되는 경우가 있다.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

from prompt_workspace.contract import check

NAME = "synthetic_cost"
TITLE = "합성 비용 데이터 보고"

SAMPLE_DESCRIPTION = (
    "우리 팀은 비용 보고를 핵심부터 읽고 싶습니다. 조회 기간과 총액을 먼저 설명하고 "
    "서비스별 금액을 정리해주세요. 비용이 크다는 이유로 낭비라고 단정하지 마세요. "
    "입력에 없는 금액, 리소스 ID, 절감액을 만들지 마세요. 개발자가 처리할 수 있게 "
    "JSON으로 받고 싶습니다."
)

SAMPLE_INPUT = {
    "period_start": "2026-09-01",
    "period_end_exclusive": "2026-10-01",
    "currency": "USD",
    "total": "37.50",
    "services": [
        {"name": "Compute", "amount": "25.00"},
        {"name": "Storage", "amount": "12.50"},
    ],
}


def _src(text: str) -> str:
    """원문 발췌. 테스트가 이 문장이 SAMPLE_DESCRIPTION 안에 실제로 있는지 본다."""
    assert text in SAMPLE_DESCRIPTION, text
    return text


def sample_requirements() -> dict[str, Any]:
    """AI 호출 없이 미리 정리해 둔 요구사항 초안. 실제 구조화 결과가 아니라
    샘플이라는 것을 화면에 밝힌다. 미결 사항 하나를 일부러 남겨 둔다 - 확인
    흐름(미결 사항이 있으면 확인 완료 불가)을 그대로 겪게 하려는 것이다."""
    return {
        "purpose": {
            "text": "조회 기간의 비용 데이터를 핵심부터 설명하고 서비스별 금액을 정리한다.",
            "origin": "extracted",
            "source_excerpt": _src("조회 기간과 총액을 먼저 설명하고 서비스별 금액을 정리해주세요."),
        },
        "variables": [
            {"name": "period_start", "description": "조회 시작일 (YYYY-MM-DD)", "type": "string",
             "required": True, "origin": "suggested", "source_excerpt": ""},
            {"name": "period_end_exclusive", "description": "조회 종료일, 이 날짜는 포함하지 않음",
             "type": "string", "required": True, "origin": "suggested", "source_excerpt": ""},
            {"name": "currency", "description": "통화 코드 (예: USD)", "type": "string",
             "required": True, "origin": "suggested", "source_excerpt": ""},
            {"name": "total", "description": "총 비용, 문자열 금액", "type": "string",
             "required": True, "origin": "extracted", "source_excerpt": _src("총액")},
            {"name": "services", "description": "서비스별 금액 목록 [{name, amount}]", "type": "array",
             "required": True, "origin": "extracted", "source_excerpt": _src("서비스별 금액")},
        ],
        "hard_rules": [
            {"id": "R1", "text": "입력에 없는 금액, 리소스 ID, 절감액을 만들지 않는다.", "origin": "extracted",
             "source_excerpt": _src("입력에 없는 금액, 리소스 ID, 절감액을 만들지 마세요.")},
            {"id": "R2", "text": "비용이 크다는 이유만으로 낭비라고 단정하지 않는다.", "origin": "extracted",
             "source_excerpt": _src("비용이 크다는 이유로 낭비라고 단정하지 마세요.")},
            {"id": "R3", "text": "총액과 통화는 입력 값을 그대로 쓴다.", "origin": "suggested",
             "source_excerpt": ""},
        ],
        "preferences": [
            {"id": "P1", "text": "조회 기간과 총액을 먼저 말하고 세부는 뒤에 둔다.", "origin": "extracted",
             "source_excerpt": _src("핵심부터 읽고 싶습니다")},
        ],
        "output_contract": {"fields": [
            {"name": "currency", "type": "string", "required": True, "description": "입력의 통화 그대로"},
            {"name": "total", "type": "string", "required": True, "description": "입력의 총액 그대로"},
            {"name": "summary", "type": "string", "required": True, "description": "한두 문장 요약"},
            {"name": "items", "type": "array", "required": True, "min_items": 0,
             "description": "서비스별 금액",
             "item_fields": [
                 {"name": "service", "type": "string", "required": True, "description": ""},
                 {"name": "amount", "type": "string", "required": True, "description": ""},
             ]},
            {"name": "limitations", "type": "array", "item_type": "string", "required": False,
             "description": "이 데이터로 판단할 수 없는 것"},
        ]},
        "open_questions": [
            {"id": "Q1", "text": "서비스 목록이 비어 있을 때(비용 0) 어떻게 답할까요? "
                                 "예: summary 에 '조회 기간에 비용이 없습니다'라고 쓰고 items 는 빈 목록."},
        ],
    }


# --- 의미 검사 ----------------------------------------------------------------


def _decimal(value: Any) -> Decimal | None:
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return None
    try:
        return Decimal(str(value).replace(",", "").strip())
    except InvalidOperation:
        return None


def check_input(values: dict[str, Any]) -> list[dict[str, str]]:
    """모델을 부르기 전에 확인이 필요한 입력. 비어 있으면 그대로 진행한다.

    합계가 맞지 않으면 고쳐서 진행하지 않고 멈춘다 (계획서 8절) - 어느 쪽이
    맞는지는 데이터를 낸 쪽이 안다."""
    problems = []
    if not str(values.get("currency") or "").strip():
        problems.append(check("통화", "fail", "currency 가 비어 있음", group="input"))
    total = _decimal(values.get("total"))
    if total is None:
        problems.append(check("총액", "fail", "total 을 금액으로 읽을 수 없음", group="input"))
    services = values.get("services")
    if not isinstance(services, list):
        problems.append(check("서비스 목록", "fail", "services 가 목록이 아님", group="input"))
        return problems
    amounts = []
    for i, item in enumerate(services):
        amount = _decimal(item.get("amount")) if isinstance(item, dict) else None
        if amount is None or not str(item.get("name") or "").strip():
            problems.append(check("서비스 목록", "fail", f"services[{i}] 에 name/amount 가 없음", group="input"))
            return problems
        amounts.append(amount)
    if total is not None and sum(amounts, Decimal(0)) != total:
        problems.append(check(
            "합계 일치", "fail",
            f"서비스 금액 합 {sum(amounts, Decimal(0))} 과 total {total} 이 다름 - 확인이 필요한 입력",
            group="input",
        ))
    return problems


_MONEY = re.compile(r"(?<![\d.])\d{1,3}(?:,\d{3})*\.\d{2}(?![\d])|(?<![\d.])\d+\.\d{2}(?![\d])")


def check_output(values: dict[str, Any], output: dict[str, Any]) -> list[dict[str, str]]:
    """출력 값이 입력과 맞는가. 형식 검사(contract.py)를 통과한 뒤에만 의미가
    있다. 설명 문장의 판단(낭비라고 단정했는지 등)은 코드로 못 재므로
    not_evaluated 로 남긴다."""
    results = []

    out_currency = output.get("currency")
    results.append(check(
        "통화 보존", "pass" if out_currency == values.get("currency") else "fail",
        "" if out_currency == values.get("currency") else f"입력 {values.get('currency')!r}, 출력 {out_currency!r}",
        group="meaning",
    ))

    in_total, out_total = _decimal(values.get("total")), _decimal(output.get("total"))
    same_total = in_total is not None and out_total == in_total
    results.append(check(
        "총액 보존", "pass" if same_total else "fail",
        "" if same_total else f"입력 {values.get('total')!r}, 출력 {output.get('total')!r}",
        group="meaning",
    ))

    expected = {s["name"]: _decimal(s["amount"]) for s in values.get("services", [])}
    got: dict[str, Decimal | None] = {}
    for item in output.get("items") or []:
        if isinstance(item, dict):
            got[str(item.get("service"))] = _decimal(item.get("amount"))
    missing = sorted(set(expected) - set(got))
    extra = sorted(set(got) - set(expected))
    wrong = sorted(n for n in set(expected) & set(got) if expected[n] != got[n])
    problems = []
    if missing:
        problems.append(f"빠진 서비스 {missing}")
    if extra:
        problems.append(f"입력에 없는 서비스 {extra}")
    if wrong:
        problems.append(f"금액이 다른 서비스 {wrong}")
    results.append(check("서비스·금액 대응", "fail" if problems else "pass", "; ".join(problems), group="meaning"))

    # 요약 문장 속 금액도 입력에 있는 값이어야 한다 (R1). 소수점 두 자리 금액만
    # 본다 - 날짜(2026-09-01)를 금액으로 잘못 읽지 않게.
    known = {v for v in [in_total, *expected.values()] if v is not None}
    stray = [m for m in _MONEY.findall(str(output.get("summary") or "")) if _decimal(m) not in known]
    results.append(check(
        "요약 속 금액 근거", "fail" if stray else "pass",
        f"입력에 없는 금액 {stray}" if stray else "소수점 두 자리 금액만 확인함",
        group="meaning",
    ))

    results.append(check(
        "설명 문장의 판단", "not_evaluated",
        "'낭비'라고 단정했는지 등은 코드로 확인하지 않음 - 수동 검토", group="meaning",
    ))
    return results
