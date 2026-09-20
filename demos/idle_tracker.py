"""AWS 비용/유휴 리소스 점검 도메인의 결정적인 데모 생성기."""

from __future__ import annotations

import re


def _request_note(source_text: str) -> str:
    note = re.sub(r"\s+", " ", source_text.strip()).replace("*/", "")
    return note[:140] or "AWS 비용에서 유휴 리소스를 찾아 주세요."


def _finding(combo: dict[str, str], service: str, resource: str, cost: str, action: str) -> str:
    if combo.get("focus", "cost") == "resource":
        lead = f"리소스 {resource} ({service})가 먼저 확인 대상입니다."
        evidence = f"이 리소스에서 최근 비용 {cost}가 발생했습니다."
    else:
        lead = f"월간 예상 낭비 비용은 {cost}입니다."
        evidence = f"원인은 {service} 리소스 {resource}의 사용 흔적이 없는 상태입니다."

    if combo.get("detail_level", "summary") == "detailed":
        return (
            f"{lead}\n{evidence}\n"
            f"해결 방법: {action}\n"
            "확인 전에는 연결된 워크로드와 백업 정책을 점검하세요."
        )
    return f"{lead}\n해결 방법: {action}"


def generate_demo(source_text: str, combo: dict[str, str]) -> str:
    note = _request_note(source_text)
    findings = [
        _finding(
            combo,
            "EC2 탄력적 IP",
            "eipalloc-0a12bc34de56f7890",
            "₩10,000",
            'AWS 콘솔 > EC2 > 탄력적 IP 메뉴에서 연결되지 않은 IP를 릴리스하세요.',
        ),
        _finding(
            combo,
            "EBS 스냅샷",
            "snap-0f1234567890abcd1",
            "₩6,800",
            'AWS 콘솔 > EC2 > 스냅샷에서 보존할 백업인지 확인한 뒤 오래된 스냅샷을 삭제하세요.',
        ),
    ]
    return (
        f"점검 요청: {note}\n\n"
        "[AWS 비용 누수 후보]\n"
        + "\n\n".join(findings)
        + "\n\n다음 결제 주기 전에 조치 여부를 다시 확인하세요."
    )
