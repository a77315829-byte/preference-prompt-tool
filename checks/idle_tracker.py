"""AWS 유휴 리소스 점검 결과를 확인하는 간단한 도메인 검사."""

from __future__ import annotations

import re


_COST_PATTERN = re.compile(r"(?:\$|₩|원|USD|달러|비용|낭비)", re.IGNORECASE)
_RESOURCE_PATTERN = re.compile(
    r"(?:i-[0-9a-f]+|eip-[0-9a-f]+|snap-[0-9a-f]+|vol-[0-9a-f]+|리소스|탄력적 IP|스냅샷|인스턴스)",
    re.IGNORECASE,
)


def detail_level(output: str, source: str, value: str, target: dict) -> tuple[float, str]:
    del source, value
    lines = [line for line in output.splitlines() if line.strip()]
    action_signals = len(re.findall(r"(?:해결|릴리스|삭제|중지|확인|콘솔)", output))
    min_lines = target.get("min_lines", 0)
    min_actions = target.get("min_actions", 0)
    score = min(1.0, len(lines) / max(min_lines, 1), action_signals / max(min_actions, 1))
    if score < 1:
        return score, f"상세도 위반: {len(lines)}줄·조치 {action_signals}개"
    return 1.0, f"상세도 충족: {len(lines)}줄·조치 {action_signals}개"


def focus(output: str, source: str, value: str, target: dict) -> tuple[float, str]:
    del source, value
    cost_signals = len(_COST_PATTERN.findall(output))
    resource_signals = len(_RESOURCE_PATTERN.findall(output))
    score = min(
        1.0,
        cost_signals / max(target.get("min_cost_signals", 1), 1),
        resource_signals / max(target.get("min_resource_signals", 1), 1),
    )
    if score < 1:
        return score, f"강조점 위반: 비용 신호 {cost_signals}개·리소스 신호 {resource_signals}개"
    return 1.0, f"강조점 충족: 비용 신호 {cost_signals}개·리소스 신호 {resource_signals}개"
