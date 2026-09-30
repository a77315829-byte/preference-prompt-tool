"""checks/idle_tracker.py 의 total_cost_accuracy·no_fabrication 회귀 테스트.

API 없이 돈다 - demos/idle_tracker.py 는 결정적 생성기라 실제 API 응답
없이도 "정확한 출력"과 "지어낸 출력"을 둘 다 만들 수 있다.
"""

from __future__ import annotations

from checks.idle_tracker import no_fabrication, total_cost_accuracy
from demos.idle_tracker import generate_demo

REPORT = {
    "totalCost": "₩16,800",
    "currency": "KRW",
    "findings": [
        {
            "service": "EC2 탄력적 IP",
            "resourceId": "eipalloc-0a12bc34de56f7890",
            "cost": "₩10,000",
            "reason": "연결되지 않은 탄력적 IP가 계속 과금되고 있습니다.",
            "resolution": "AWS 콘솔 > EC2 > 탄력적 IP 메뉴에서 릴리스하세요.",
        },
        {
            "service": "EBS 스냅샷",
            "resourceId": "snap-0f1234567890abcd1",
            "cost": "₩6,800",
            "reason": "오래된 스냅샷이 남아 있어 저장 비용이 발생합니다.",
            "resolution": "AWS 콘솔 > EC2 > 스냅샷에서 필요 없는 항목을 확인 후 삭제하세요.",
        },
    ],
}


def test_demo_generator_output_passes_both_checks() -> None:
    """demos/idle_tracker.py 는 REPORT 의 실제 값만 쓰므로 두 검사 모두
    통과해야 한다 - API 응답 없이도 검사 함수 자체의 정확성을 확인한다."""
    for combo in (
        {"detail_level": "summary", "focus": "cost"},
        {"detail_level": "detailed", "focus": "resource"},
    ):
        output = generate_demo("점검해줘", combo)
        cost_score, cost_note = total_cost_accuracy(output, REPORT)
        fab_score, fab_note = no_fabrication(output, REPORT)
        assert fab_score == 1.0, f"{combo}: {fab_note}"
        # detail_level=summary 는 합계 금액을 안 낼 수도 있다 - "검사 생략"도 1.0.
        assert cost_score == 1.0, f"{combo}: {cost_note}"


def test_no_fabrication_catches_a_made_up_dollar_amount() -> None:
    fabricated = "총 예상 비용은 ₩99,999입니다. eipalloc-0a12bc34de56f7890 를 확인하세요."
    score, note = no_fabrication(fabricated, REPORT)
    assert score == 0.0, note
    assert "99999" in note or "99,999" in note or "금액" in note


def test_no_fabrication_catches_a_made_up_resource_id() -> None:
    fabricated = "eipalloc-deadbeef00000000 리소스에서 ₩10,000 이 발생했습니다."
    score, note = no_fabrication(fabricated, REPORT)
    assert score == 0.0, note
    assert "리소스id" in note.lower() or "리소스" in note


def test_no_fabrication_allows_known_values_only() -> None:
    honest = "탄력적 IP(eipalloc-0a12bc34de56f7890)에서 ₩10,000 이 발생했습니다."
    score, note = no_fabrication(honest, REPORT)
    assert score == 1.0, note


def test_total_cost_accuracy_flags_a_wrong_total() -> None:
    wrong_total = "이번 달 총 비용은 ₩20,000 입니다."
    score, note = total_cost_accuracy(wrong_total, REPORT)
    assert score == 0.0, note


def test_total_cost_accuracy_accepts_currency_variants() -> None:
    # ₩16,800 과 "16800원" 은 같은 값으로 봐야 한다.
    won_form = "총 비용은 16800원 입니다."
    score, note = total_cost_accuracy(won_form, REPORT)
    assert score == 1.0, note
