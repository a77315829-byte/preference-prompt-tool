"""AWS 비용 현황 리포트(idle_tracker) 도메인의 결정적인 데모 생성기."""

from __future__ import annotations

import re
from typing import Any

# 확정된 $45.20 표준 데모 데이터 기준 4종 리포트 (4단 고정 레이아웃)
_REPORTS_4520: dict[tuple[str, str], str] = {
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

def _request_note(source_text: str) -> str:
    note = re.sub(r"\s+", " ", source_text.strip()).replace("*/", "")
    return note[:140] or "AWS 비용에서 유휴 리소스를 찾아 주세요."

def _legacy_finding(combo: dict[str, str], service: str, resource: str, cost: str, action: str) -> str:
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

    # 신규 2개 축(format, scope)이 지정된 경우 확정된 $45.20 4단 레이아웃 리포트를 반환한다.
    if "format" in combo or "scope" in combo:
        fmt = combo.get("format", "bullet_list")
        if fmt not in ("bullet_list", "markdown_table"):
            fmt = "bullet_list"
        scp = combo.get("scope", "summary_brief")
        if scp not in ("summary_brief", "deep_dive"):
            scp = "summary_brief"
        return _REPORTS_4520[(fmt, scp)]

    # 구버전 축(detail_level, focus)으로 호출된 경우 기존 회귀 테스트 호환을 위해 유지한다.
    note = _request_note(source)
    findings = [
        _legacy_finding(
            combo,
            "EC2 탄력적 IP",
            "eipalloc-0a12bc34de56f7890",
            "₩10,000",
            "AWS 콘솔 > EC2 > 탄력적 IP 메뉴에서 연결되지 않은 IP를 릴리스하세요.",
        ),
        _legacy_finding(
            combo,
            "EBS 스냅샷",
            "snap-0f1234567890abcd1",
            "₩6,800",
            "AWS 콘솔 > EC2 > 스냅샷에서 보존할 백업인지 확인한 뒤 오래된 스냅샷을 삭제하세요.",
        ),
    ]
    return (
        f"점검 요청: {note}\n\n"
        "[AWS 비용 누수 후보]\n"
        + "\n\n".join(findings)
        + "\n\n다음 결제 주기 전에 조치 여부를 다시 확인하세요."
    )

# 엔진이 generate_demo 라는 함수명을 찾을 경우를 대비한 별칭
generate_demo = generate