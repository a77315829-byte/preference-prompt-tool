"""AWS 비용 현황 리포트(idle_tracker) 도메인 채점표 및 팩트 정확성 검사.

`format`·`scope`는 축 검사(취향 - A/B 비교로 학습)이며, GEPA 성찰에 쓰이는
점수(0.0~1.0)와 구체적인 위반 피드백 문자열을 반환한다.
`total_cost_accuracy`·`no_fabrication`은 취향이 아닌 필수 불변 조건(금액·리소스ID
일치 및 추측 금지)을 검증한다.
"""

from __future__ import annotations

import re
from typing import Any

_COST_PATTERN = re.compile(r"(?:\$|₩|원|USD|달러|비용|낭비|청구)", re.IGNORECASE)
_RESOURCE_PATTERN = re.compile(
    r"(?:i-[0-9a-f]+|eip-[0-9a-f]+|snap-[0-9a-f]+|vol-[0-9a-f]+|"
    r"APN2-[A-Za-z0-9:._-]+|BoxUsage:[A-Za-z0-9._-]+|EBS:[A-Za-z0-9._-]+|"
    r"InstanceUsage:[A-Za-z0-9._-]+|RDS:[A-Za-z0-9._-]+|TimedStorage-[A-Za-z0-9._-]+|"
    r"DataTransfer-[A-Za-z0-9._-]+|HostedZone|리소스|탄력적 IP|스냅샷|인스턴스)",
    re.IGNORECASE,
)

# 출력에서 실제로 언급된 금액·리소스ID를 뽑아 원본 데이터와 대조한다.
_MONEY_TOKEN = re.compile(r"[₩$]\s?[\d,]+(?:\.\d+)?|\d[\d,]*\s?(?:원|달러|USD)")
_RESOURCE_ID_TOKEN = re.compile(r"\b(?:i|eip|eipalloc|snap|vol)-[0-9a-f]{6,}\b", re.IGNORECASE)
_USAGE_TYPE_TOKEN = re.compile(
    r"\b(?:APN2-[A-Za-z0-9:._-]+|BoxUsage:[A-Za-z0-9._-]+|EBS:[A-Za-z0-9._-]+|"
    r"InstanceUsage:[A-Za-z0-9._-]+|RDS:[A-Za-z0-9._-]+|TimedStorage-[A-Za-z0-9._-]+|"
    r"DataTransfer-[A-Za-z0-9._-]+|HostedZone)\b"
)
_TOTAL_PHRASE = re.compile(r"(?:총|합계|전체)\s*(?:예상\s*|청구\s*)?(?:비용|낭비|금액|합계)")
_SPECULATION_PATTERN = re.compile(
    r"(?:깜빡\s*잊고|실수로\s*켜둔|방치된\s*것이\s*확실|무조건\s*삭제하세요|즉시\s*종료하세요)"
)
_TABLE_DIVIDER = re.compile(r"^\s*\|(?:\s*:?-{2,}:?\s*\|)+\s*$", re.MULTILINE)
_BULLET_LINE = re.compile(r"^\s*[-*]\s+\S+", re.MULTILINE)


def _unpack_target(target: dict[str, Any] | None, kwargs: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    if isinstance(target, dict):
        merged.update(target)
    merged.update(kwargs)
    return merged


def _normalize_money(text: str) -> str:
    """"₩10,000"과 "10000원", "$45.20"을 숫자 문자열로 정규화한다."""
    digits = re.sub(r"[^\d]", "", text)
    return digits.lstrip("0") or "0"


def _known_figures(report: dict) -> tuple[set[str], set[str]]:
    money = {_normalize_money(str(report.get("totalCost", "")))}
    for extra_key in ("topSummary", "otherSummary", "momComparison"):
        for token in _MONEY_TOKEN.findall(str(report.get(extra_key, ""))):
            money.add(_normalize_money(token))

    ids: set[str] = set()
    for finding in report.get("findings", []):
        money.add(_normalize_money(str(finding.get("cost", ""))))
        for field_name in ("resourceId", "reason"):
            raw_field = str(finding.get(field_name, ""))
            for token in _MONEY_TOKEN.findall(raw_field):
                money.add(_normalize_money(token))
            for match in _RESOURCE_ID_TOKEN.finditer(raw_field):
                ids.add(match.group(0).lower())
    money.discard("0")
    return money, ids


def _extract_section_2(output: str) -> str:
    """4단 레이아웃 중 '## 2.' 과금 내역 본문만 추출한다. 헤더가 없으면 전체를 반환한다."""
    match = re.search(r"##\s*2\.[^\n]*\n(.*?)(?=\n##\s*3\.|\Z)", output, re.DOTALL)
    if match:
        return match.group(1).strip()
    return output.strip()


def total_cost_accuracy(output: str, report: dict) -> tuple[float, str]:
    """"총 비용은 X" 처럼 합계를 주장하는 문구가 있으면, 그 X가 실제
    합계와 일치해야 한다. 항목별 비용만 나열하고 합계를 안 밝히는 것은
    틀린 게 아니라서 검사하지 않는다 - 그건 no_fabrication의 일이다."""
    expected = _normalize_money(str(report.get("totalCost", "")))
    if expected == "0":
        return 1.0, "합계 비용 데이터가 없어 검사를 생략한다."

    for match in _TOTAL_PHRASE.finditer(output):
        window = output[match.end() : match.end() + 40]
        money = _MONEY_TOKEN.search(window)
        if not money:
            continue
        if _normalize_money(money.group(0)) == expected:
            return 1.0, f"합계 비용 {report.get('totalCost')} 이 정확히 언급됐다."
        return 0.0, (
            f"'{match.group(0)}' 뒤에 {money.group(0)} 이라 적었지만 "
            f"실제 합계는 {report.get('totalCost')} 다."
        )
    return 1.0, "합계를 명시적으로 주장하지 않았다 - 검사 대상이 아니다."


def no_fabrication(output: str, report: dict) -> tuple[float, str]:
    """출력에 나온 금액·리소스ID가 전부 원본 조회 데이터에 있어야 한다.
    데이터에 없는 값이 하나라도 있으면 모델이 지어낸 것이다."""
    if _SPECULATION_PATTERN.search(output):
        return 0.0, "원본 데이터에 근거가 없는 유휴 단정(추측성 표현)이 포함됐다."

    known_money, known_ids = _known_figures(report)
    mentioned_money = {_normalize_money(m) for m in _MONEY_TOKEN.findall(output)}
    mentioned_ids = {m.lower() for m in _RESOURCE_ID_TOKEN.findall(output)}

    fabricated_money = mentioned_money - known_money - {"0"}
    fabricated_ids = mentioned_ids - known_ids

    if fabricated_money or fabricated_ids:
        parts = []
        if fabricated_money:
            parts.append(f"금액 {sorted(fabricated_money)}")
        if fabricated_ids:
            parts.append(f"리소스ID {sorted(fabricated_ids)}")
        return 0.0, f"원본 데이터에 없는 값을 만들어냈다: {', '.join(parts)}"
    return 1.0, "출력의 모든 금액·리소스ID가 원본 조회 데이터와 일치한다."


def format(output: str, source: str, value: str, target: dict) -> tuple[float, str]:
    """출력 형식(format) 축 채점표: bullet_list vs markdown_table."""
    del source
    style = target.get("style", value or "bullet_list")
    body = _extract_section_2(output)

    has_table = bool(_TABLE_DIVIDER.search(body)) or body.count("|") >= 6
    bullet_count = len(_BULLET_LINE.findall(body))

    if style == "bullet_list":
        if not target.get("allow_table", False) and has_table:
            return 0.0, "출력 형식 위반: 개조식 불릿 리스트만 써야 하는데 마크다운 표(|)가 포함됨"
        if bullet_count < 2:
            return 0.5, f"출력 형식 위반: 개조식 불릿 항목이 {bullet_count}개뿐임 (최소 2개 이상 필요)"
        return 1.0, f"출력 형식 충족: 개조식 불릿 리스트({bullet_count}개 항목)로 작성됨"

    if style == "markdown_table":
        if not has_table:
            return 0.0, "출력 형식 위반: 마크다운 표(| 헤더 | 및 구분선) 레이아웃이 없음"
        if target.get("require_total_row", True):
            if not any(kw in body for kw in ("합계", "총계", "Total", "전체 비용")):
                return 0.5, "출력 형식 부분 위반: 마크다운 표는 있으나 마지막 '| **합계** |' 행이 누락됨"
        return 1.0, "출력 형식 충족: 마크다운 표 및 합계 행이 정확히 포함됨"

    return 0.0, f"알 수 없는 출력 형식 목표값: {style}"


def scope(output: str, source: str, value: str, target: dict) -> tuple[float, str]:
    """보고 성향 및 범위(scope) 축 채점표: summary_brief vs deep_dive."""
    level = target.get("level", value or "summary_brief")
    body = _extract_section_2(output)

    has_etc_group = any(
        phrase in output
        for phrase in ("기타 서비스 합계", "기타 합계", "소액 항목 통합", "외 1건", "외 2건")
    )
    usage_matches = _USAGE_TYPE_TOKEN.findall(body) + _RESOURCE_ID_TOKEN.findall(body)

    if level == "summary_brief":
        if target.get("require_etc_group", True) and not has_etc_group:
            return 0.0, "보고 범위 위반: 핵심 요약형(summary_brief)은 소액 항목을 '기타 서비스 합계'로 묶어야 함"
        if len(usage_matches) > 2:
            return 0.5, f"보고 범위 위반: 핵심 요약형인데 세부 Usage Type 코드가 {len(usage_matches)}개 나열됨 (생략 필요)"
        return 1.0, "보고 범위 충족: 상위 핵심 서비스만 요약하고 나머지를 '기타 서비스 합계'로 통합함"

    if level == "deep_dive":
        if has_etc_group and len(usage_matches) == 0:
            return 0.0, "보고 범위 위반: 전체 상세형(deep_dive)인데 항목을 '기타 합계'로 묶어 생략함"
        source_usages = _USAGE_TYPE_TOKEN.findall(source) + _RESOURCE_ID_TOKEN.findall(source)
        required = int(target.get("min_usage_types", 4))
        if source_usages:
            required = min(required, len(source_usages))
        found = len(usage_matches)
        if found < required:
            score = round(found / max(required, 1), 2)
            return score, f"보고 범위 위반: 세부 Usage Type·리소스 코드가 {found}개만 표시됨 (목표 {required}개 이상)"
        return 1.0, f"보고 범위 충족: 전체 서비스 및 세부 Usage Type({found}개)이 빠짐없이 나열됨"

    return 0.0, f"알 수 없는 보고 범위 목표값: {level}"


# ---------------------------------------------------------------------------
# 구버전 축(detail_level, focus) 하위 호환 유지
# ---------------------------------------------------------------------------

def detail_level(output: str, source: str, value: str, target: dict = None) -> tuple[float, str]:
    del source, value
    target = target or {}
    lines = [line for line in output.splitlines() if line.strip()]
    action_signals = len(re.findall(r"(?:해결|릴리스|삭제|중지|확인|콘솔)", output))
    min_lines = target.get("min_lines", 0)
    min_actions = target.get("min_actions", 0)
    score = min(1.0, len(lines) / max(min_lines, 1), action_signals / max(min_actions, 1))
    if score < 1:
        return score, f"상세도 위반: {len(lines)}줄·조치 {action_signals}개"
    return 1.0, f"상세도 충족: {len(lines)}줄·조치 {action_signals}개"


def focus(output: str, source: str, value: str, target: dict = None) -> tuple[float, str]:
    del source, value
    target = target or {}
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