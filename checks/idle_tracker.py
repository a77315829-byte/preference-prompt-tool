"""AWS 유휴 리소스 점검 결과를 확인하는 간단한 도메인 검사.

`detail_level`·`focus`는 축 검사(취향 - 8회 비교로 학습)다. 아래
`total_cost_accuracy`·`no_fabrication`은 축이 아니다 - 취향이 아니라
필수조건이라서다. 상세하게 쓰든 짧게 쓰든, 비용 중심으로 강조하든
리소스 중심으로 강조하든, 출력에 나오는 금액·리소스ID는 실제 조회
데이터와 맞아야 한다. 그래서 `metric_builder`의 축 가중 채점에 넣지
않고, `engine/metric_builder.py`가 모르는 여기 별도 함수로 둔다(엔진은
"축이 있다"까지만 안다 - 절대 규칙 1). `experiments/idle_tracker_accuracy.py`
가 이 함수들로 실제 생성 결과를 검증한다."""

from __future__ import annotations

import re


_COST_PATTERN = re.compile(r"(?:\$|₩|원|USD|달러|비용|낭비)", re.IGNORECASE)
_RESOURCE_PATTERN = re.compile(
    r"(?:i-[0-9a-f]+|eip-[0-9a-f]+|snap-[0-9a-f]+|vol-[0-9a-f]+|리소스|탄력적 IP|스냅샷|인스턴스)",
    re.IGNORECASE,
)

# 출력에서 실제로 언급된 금액·리소스ID를 뽑아 원본 데이터와 대조한다.
_MONEY_TOKEN = re.compile(r"[₩$]\s?[\d,]+(?:\.\d+)?|\d[\d,]*\s?(?:원|달러|USD)")
_RESOURCE_ID_TOKEN = re.compile(r"\b(?:i|eip|eipalloc|snap|vol)-[0-9a-f]{6,}\b", re.IGNORECASE)
# "총 비용은 X"처럼 합계를 주장하는 문구 뒤에 오는 금액만 본다. 항목별
# 비용만 나열하고 합계를 아예 안 밝히는 것(요약형 출력에서 흔함)은 틀린
# 게 아니다 - 실측에서 demos/idle_tracker.py 조차 요약 모드에선 합계를
# 안 말한다는 걸 확인했다.
_TOTAL_PHRASE = re.compile(r"(?:총|합계|전체)\s*(?:예상\s*)?(?:비용|낭비|금액)")


def _normalize_money(text: str) -> str:
    """"₩10,000"과 "10000원"을 같은 값으로 보려고 숫자만 남긴다."""
    digits = re.sub(r"[^\d]", "", text)
    return digits.lstrip("0") or "0"


def _known_figures(report: dict) -> tuple[set[str], set[str]]:
    money = {_normalize_money(str(report.get("totalCost", "")))}
    ids = set()
    for finding in report.get("findings", []):
        money.add(_normalize_money(str(finding.get("cost", ""))))
        rid = str(finding.get("resourceId", ""))
        match = _RESOURCE_ID_TOKEN.search(rid)
        if match:
            ids.add(match.group(0).lower())
    money.discard("0")
    return money, ids


def total_cost_accuracy(output: str, report: dict) -> tuple[float, str]:
    """"총 비용은 X" 처럼 합계를 주장하는 문구가 있으면, 그 X가 실제
    합계와 일치해야 한다. 항목별 비용만 나열하고 합계를 안 밝히는 것은
    틀린 게 아니라서 검사하지 않는다 - 그건 no_fabrication의 일이다."""
    expected = _normalize_money(str(report.get("totalCost", "")))
    if expected == "0":
        return 1.0, "합계 비용 데이터가 없어 검사를 생략한다."

    for match in _TOTAL_PHRASE.finditer(output):
        window = output[match.end(): match.end() + 30]
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
