"""AWS 비용 분석 리포트(idle_tracker) 규칙 기반 데모 후보 생성기.

API 호출 없이도(demo_mode=True) 사용자가 format(개조식 vs 표)과
scope(핵심 요약 vs 전체 상세) 2개 축의 차이를 명확히 비교할 수 있도록
4단 고정 레이아웃 기반의 리포트를 결정론적으로 생성한다.
"""

from __future__ import annotations

import re
from typing import Any

# 확정된 $45.20 표준 데모 데이터 기준 4종 리포트 템플릿
_STANDARD_REPORTS: dict[tuple[str, str], str] = {
    ("bullet_list", "summary_brief"): """\
# [AWS 비용 분석 리포트]
> - **조회 기간:** 2026-10-01 ~ 2026-10-15 (진행 중인 달 / 추정치)
> - **갱신 시각:** 2026-10-16 00:00 UTC | **계정 ID:** 1234-****-9012 | **통화:** USD

## 1. 총 청구 금액
- **총 합계:** **$45.20** (세금 및 크레딧 제외)

## 2. 핵심 과금 내역 (요약)
- **Amazon EC2:** $25.00 (55.3%) — 주요 리전: ap-northeast-2
- **Amazon RDS:** $15.00 (33.2%) — 주요 리전: ap-northeast-2
- **기타 서비스 합계 (2건):** $5.20 (11.5%) — Amazon S3 외 1개 소액 항목 통합

## 3. 데이터 확인 안내
- 본 리포트는 AWS 최신 가용 비용 데이터를 기반으로 작성되었습니다. 개별 리소스의 실제 유휴(Idle) 여부나 삭제 가능 여부는 청구 데이터만으로 단정할 수 없으므로, AWS 콘솔(CloudWatch 지표 등)에서 추가 확인이 필요합니다.""",

    ("markdown_table", "summary_brief"): """\
# [AWS 비용 분석 리포트]
> - **조회 기간:** 2026-10-01 ~ 2026-10-15 (진행 중인 달 / 추정치)
> - **갱신 시각:** 2026-10-16 00:00 UTC | **계정 ID:** 1234-****-9012 | **통화:** USD

## 1. 총 청구 금액
- **총 합계:** **$45.20** (세금 및 크레딧 제외)

## 2. 핵심 과금 내역 (요약)
| 구분 | 서비스명 | 주요 리전 | 청구 금액 | 전체 비중 |
| :---: | :--- | :--- | :---: | :---: |
| 핵심 1 | **Amazon EC2** | ap-northeast-2 | $25.00 | 55.3% |
| 핵심 2 | **Amazon RDS** | ap-northeast-2 | $15.00 | 33.2% |
| 기타 | **기타 서비스 합계 (2건)** | 통합 | $5.20 | 11.5% |
| **합계** | **전체 비용** | **-** | **$45.20** | **100.0%** |

## 3. 데이터 확인 안내
- 본 리포트는 AWS 최신 가용 비용 데이터를 기반으로 작성되었습니다. 개별 리소스의 실제 유휴(Idle) 여부나 삭제 가능 여부는 청구 데이터만으로 단정할 수 없으므로, AWS 콘솔(CloudWatch 지표 등)에서 추가 확인이 필요합니다.""",

    ("bullet_list", "deep_dive"): """\
# [AWS 비용 분석 리포트]
> - **조회 기간:** 2026-10-01 ~ 2026-10-15 (진행 중인 달 / 추정치)
> - **갱신 시각:** 2026-10-16 00:00 UTC | **계정 ID:** 1234-****-9012 | **통화:** USD

## 1. 총 청구 금액
- **총 합계:** **$45.20** (세금 및 크레딧 제외)

## 2. 전체 과금 상세 내역 (Usage Type 기준)
- **Amazon EC2:** $25.00 (55.3%)
  - `[ap-northeast-2]` `APN2-BoxUsage:t2.micro`: $20.00
  - `[ap-northeast-2]` `APN2-EBS:VolumeUsage.gp2`: $5.00
- **Amazon RDS:** $15.00 (33.2%)
  - `[ap-northeast-2]` `APN2-InstanceUsage:db.t2.micro`: $12.00
  - `[ap-northeast-2]` `APN2-RDS:GP2-Storage`: $3.00
- **Amazon S3:** $5.00 (11.1%)
  - `[ap-northeast-2]` `APN2-TimedStorage-ByteHrs`: $4.50
  - `[ap-northeast-2]` `APN2-DataTransfer-Out-Bytes`: $0.50
- **Amazon Route53:** $0.20 (0.4%)
  - `[Global]` `HostedZone`: $0.20

## 3. 데이터 확인 안내
- 위 내역은 제공된 사용 유형(Usage Type) 및 리전 기준의 전체 팩트 데이터입니다. 특정 리소스의 활성 상태나 낭비 원인은 포함되어 있지 않으므로, 비용 절감 조치 전 AWS 콘솔에서 실제 트래픽 및 이용률을 추가 확인하시기 바랍니다.""",

    ("markdown_table", "deep_dive"): """\
# [AWS 비용 분석 리포트]
> - **조회 기간:** 2026-10-01 ~ 2026-10-15 (진행 중인 달 / 추정치)
> - **갱신 시각:** 2026-10-16 00:00 UTC | **계정 ID:** 1234-****-9012 | **통화:** USD

## 1. 총 청구 금액
- **총 합계:** **$45.20** (세금 및 크레딧 제외)

## 2. 전체 과금 상세 내역 (Usage Type 기준)
| 서비스명 | 리전 (Region) | 사용 유형 (Usage Type) | 세부 금액 | 서비스 소계 | 비중 |
| :--- | :--- | :--- | :---: | :---: | :---: |
| **Amazon EC2** | ap-northeast-2 | `APN2-BoxUsage:t2.micro` | $20.00 | $25.00 | 55.3% |
| **Amazon EC2** | ap-northeast-2 | `APN2-EBS:VolumeUsage.gp2` | $5.00 | (위와 합산) | - |
| **Amazon RDS** | ap-northeast-2 | `APN2-InstanceUsage:db.t2.micro` | $12.00 | $15.00 | 33.2% |
| **Amazon RDS** | ap-northeast-2 | `APN2-RDS:GP2-Storage` | $3.00 | (위와 합산) | - |
| **Amazon S3** | ap-northeast-2 | `APN2-TimedStorage-ByteHrs` | $4.50 | $5.00 | 11.1% |
| **Amazon S3** | ap-northeast-2 | `APN2-DataTransfer-Out-Bytes` | $0.50 | (위와 합산) | - |
| **Route53** | Global | `HostedZone` | $0.20 | $0.20 | 0.4% |
| **합계** | **-** | **전체 7개 사용 유형** | **$45.20** | **$45.20** | **100.0%** |

## 3. 데이터 확인 안내
- 위 내역은 제공된 사용 유형(Usage Type) 및 리전 기준의 전체 팩트 데이터입니다. 특정 리소스의 활성 상태나 낭비 원인은 포함되어 있지 않으므로, 비용 절감 조치 전 AWS 콘솔에서 실제 트래픽 및 이용률을 추가 확인하시기 바랍니다.""",
}

_ITEM_LINE_RE = re.compile(
    r"^-\s*(?P<service>[^(\n:]+?)\s*\((?P<resource>[^)]+)\)\s*:\s*(?P<cost>\$\d[\d,]*(?:\.\d+)?|₩\d[\d,]*)\s*(?:-\s*(?P<detail>.*))?$"
)


def _normalize_combo(combo: dict[str, str]) -> tuple[str, str]:
    """신규 축(format, scope) 및 구버전 축(detail_level, focus) 입력을 모두 표준 키로 변환한다."""
    fmt = combo.get("format")
    scp = combo.get("scope")

    if fmt not in ("bullet_list", "markdown_table"):
        # 구버전 focus 축 호환: resource는 표, cost는 불릿으로 매핑
        fmt = "markdown_table" if combo.get("focus") == "resource" else "bullet_list"

    if scp not in ("summary_brief", "deep_dive"):
        # 구버전 detail_level 축 호환
        scp = "deep_dive" if combo.get("detail_level") == "detailed" else "summary_brief"

    return fmt, scp


def _render_custom_source(source: str, fmt: str, scp: str) -> str | None:
    """원문이 $45.20 표준 데이터가 아닌 경우(예: api_server 기본 ₩16,800 데모 등),
    원문의 금액과 리소스 ID만 인용하여 4단 레이아웃으로 동적 조립한다."""
    if "$45.20" in source or not source.strip():
        return None

    period_match = re.search(r"조회\s*기간\s*:\s*([^\n]+)", source)
    total_match = re.search(r"총\s*(?:예상|청구)\s*(?:비용|금액)\s*:\s*(\$\d[\d,]*(?:\.\d+)?|₩\d[\d,]*)", source)

    items: list[dict[str, str]] = []
    for line in source.splitlines():
        m = _ITEM_LINE_RE.match(line.strip())
        if m:
            items.append(m.groupdict())

    if not total_match and not items:
        return None

    period = period_match.group(1).strip() if period_match else "최근 30일 (가용 데이터 기준)"
    total_cost = total_match.group(1).strip() if total_match else (items[0]["cost"] if items else "$0.00")
    currency = "KRW" if "₩" in total_cost else "USD"

    header = (
        "# [AWS 비용 분석 리포트]\n"
        f"> - **조회 기간:** {period}\n"
        f"> - **계정 ID:** 1234-****-9012 | **통화:** {currency}\n\n"
        "## 1. 총 청구 금액\n"
        f"- **총 합계:** **{total_cost}**\n\n"
    )
    footer = (
        "\n\n## 3. 데이터 확인 안내\n"
        "- 본 리포트는 제공된 AWS 비용 조회 데이터에 포함된 금액과 리소스만 인용하여 작성되었습니다. "
        "실제 유휴 상태 및 삭제 전 의존 관계는 AWS 콘솔에서 추가 확인하시기 바랍니다."
    )

    if scp == "summary_brief":
        section_title = "## 2. 핵심 과금 내역 (요약)\n"
        top_item = items[0] if items else {"service": "주요 서비스", "resource": "-", "cost": total_cost}
        rest_count = max(0, len(items) - 1)
        if fmt == "bullet_list":
            body = (
                f"- **{top_item['service']}:** {top_item['cost']} — 주요 항목\n"
                f"- **기타 서비스 합계 ({rest_count}건):** 나머지 항목 통합 (총액 {total_cost} 내 포함)"
            )
        else:
            body = (
                "| 구분 | 서비스명 | 청구 금액 | 비고 |\n"
                "| :---: | :--- | :---: | :--- |\n"
                f"| 핵심 1 | **{top_item['service']}** | {top_item['cost']} | 주요 과금 항목 |\n"
                f"| 기타 | **기타 서비스 합계 ({rest_count}건)** | 통합 | 소액 항목 통합 |\n"
                f"| **합계** | **전체 비용** | **{total_cost}** | **100.0%** |"
            )
    else:
        section_title = "## 2. 전체 과금 상세 내역 (Usage Type 기준)\n"
        if fmt == "bullet_list":
            bullets = [
                f"- **{it['service']} ({it['resource']}):** {it['cost']} — {it.get('detail') or '상세 내역 확인'}"
                for it in items
            ] or [f"- **전체 항목:** {total_cost}"]
            body = "\n".join(bullets)
        else:
            rows = [
                "| 서비스명 | 리소스 / 사용 유형 | 청구 금액 | 상세 안내 |",
                "| :--- | :--- | :---: | :--- |",
            ]
            for it in items:
                rows.append(
                    f"| **{it['service']}** | `{it['resource']}` | {it['cost']} | {it.get('detail') or '-'} |"
                )
            rows.append(f"| **합계** | **전체 {len(items)}개 항목** | **{total_cost}** | **100.0%** |")
            body = "\n".join(rows)

    return header + section_title + body + footer


def generate(*args: Any, **kwargs: Any) -> str:
    """엔진의 demo_generator가 호출하는 진입점.

    호출 시그니처가 (source, combo)이든 (domain, source, combo)이든 모두 지원한다.
    """
    source = ""
    combo: dict[str, str] = {}

    if len(args) == 2 and isinstance(args[0], str) and isinstance(args[1], dict):
        source, combo = args[0], args[1]
    elif len(args) >= 3 and isinstance(args[1], str) and isinstance(args[2], dict):
        source, combo = args[1], args[2]
    else:
        source = str(kwargs.get("source", args[0] if args and isinstance(args[0], str) else ""))
        combo = dict(kwargs.get("combo", {}))

    fmt, scp = _normalize_combo(combo)
    custom = _render_custom_source(source, fmt, scp)
    if custom is not None:
        return custom
    return _STANDARD_REPORTS[(fmt, scp)]


# 엔진이 generate_demo 라는 함수명을 찾을 경우를 대비한 별칭
generate_demo = generate