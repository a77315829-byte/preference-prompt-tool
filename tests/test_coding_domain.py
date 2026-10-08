"""코딩 도메인의 선택·평가·프롬프트 조립 검증."""

import itertools

import api_server
import service
from checks.coding import count_files, count_theme_signals, count_type_signals
from demos.coding import demo_scenario
from engine.demo_generator import generate_demo
from engine.domain_loader import load_domain
from engine.estimator import Comparison, Estimator
from engine.metric_builder import build_metric
from engine.selector import UncertaintySelector
from optimize.run_gepa import build_seed_prompt


REQUEST = "클릭 횟수를 보여주는 버튼 컴포넌트를 만들어 주세요."
PREFERRED = {
    "code_structure": "separated",
    "style_management": "theme",
    "type_detail": "explicit",
}
OPPOSITE = {
    "code_structure": "compact",
    "style_management": "direct",
    "type_detail": "inferred",
}


def _matches(combo: dict[str, str], target: dict[str, str]) -> int:
    return sum(combo.get(name) == value for name, value in target.items())


def test_coding_domain_has_three_axes() -> None:
    domain = load_domain("domains/coding.yaml")

    assert domain.name == "coding"
    assert [axis.name for axis in domain.axes] == [
        "code_structure",
        "style_management",
        "type_detail",
    ]


def test_demo_changes_with_each_axis_and_is_deterministic() -> None:
    domain = load_domain("domains/coding.yaml")
    base = generate_demo(domain, REQUEST, OPPOSITE)

    assert base == generate_demo(domain, REQUEST, OPPOSITE)
    for axis_name, value in PREFERRED.items():
        changed = {**OPPOSITE, axis_name: value}
        assert generate_demo(domain, REQUEST, changed) != base


def test_demo_examples_follow_supported_development_requests() -> None:
    domain = load_domain("domains/coding.yaml")
    cases = [
        ("검색어로 상품 목록을 필터링해 주세요", "ProductSearch", "products.filter"),
        ("확인 모달을 만들어 주세요", "ConfirmDialog", 'role="dialog"'),
        ("API에서 사용자 프로필을 가져오는 훅", "ProfileCard", 'fetch("/api/profile"'),
    ]
    for request, component, behavior in cases:
        for structure in ("compact", "separated"):
            combo = {
                "code_structure": structure,
                "style_management": "theme",
                "type_detail": "explicit",
            }
            output = generate_demo(domain, request, combo)
            assert component in output
            assert behavior in output
            assert "PreferenceButton" not in output
            assert output == generate_demo(domain, request, combo)


def test_unmatched_demo_request_discloses_style_only_fallback() -> None:
    domain = load_domain("domains/coding.yaml")
    output = generate_demo(domain, "달력 예약 화면을 만들어 주세요", {})
    assert "데모 안내" in output
    assert "버튼 예시로 코딩 스타일만 비교" in output
    assert demo_scenario("검색 기능을 만들어 주세요") is None
    assert demo_scenario("확인 버튼을 만들어 주세요") is None


def test_supported_demo_keeps_behavior_across_all_style_combinations() -> None:
    domain = load_domain("domains/coding.yaml")
    cases = [
        ("클릭 횟수를 보여주는 버튼", "count", "increment"),
        ("상품 검색 목록을 필터링", "products.filter", "상품 검색"),
        ("확인 모달을 만들어 주세요", 'role="dialog"', "진행하시겠어요?"),
        ("프로필 가져오기", 'fetch("/api/profile"', "불러오는 중"),
    ]
    for request, behavior, label in cases:
        assert demo_scenario(request) is not None
        for structure, style, typing in itertools.product(
            ("compact", "separated"), ("direct", "theme"), ("inferred", "explicit")
        ):
            combo = {"code_structure": structure, "style_management": style, "type_detail": typing}
            output = generate_demo(domain, request, combo)
            assert behavior in output and label in output
            assert count_files(output) == (1 if structure == "compact" else 3)
            assert (count_theme_signals(output) >= 2) == (style == "theme")
            assert (count_type_signals(output) >= 5) == (typing == "explicit")
            assert output == generate_demo(domain, request, combo)


def test_demo_session_exposes_supported_or_fallback_status() -> None:
    for request, expected in (("확인 모달", "modal"), ("예약 달력", None)):
        state = service.start_session(
            request, "coding", "domains/coding.yaml", model="unused", demo_mode=True
        )
        payload = api_server._state_payload(state)
        assert payload["coding_demo_scenario"] == expected
        assert payload["pair"]["a"]["text"]


def test_eight_comparisons_restore_hidden_preferences() -> None:
    domain = load_domain("domains/coding.yaml")
    estimator = Estimator(domain)
    selector = UncertaintySelector(domain, seed=0)

    for _ in range(8):
        combo_a, combo_b = selector.next_pair(estimator)
        winner = "a" if _matches(combo_a, PREFERRED) >= _matches(combo_b, PREFERRED) else "b"
        estimator.update(Comparison(combo_a, combo_b, winner))

    restored = {name: estimator.preferred_value(name) for name in estimator.enum_axis_names()}
    assert restored == PREFERRED


def test_matching_code_scores_higher_and_prompt_matches_choices() -> None:
    domain = load_domain("domains/coding.yaml")
    estimator = Estimator(domain)
    for _ in range(12):
        estimator.update(Comparison(PREFERRED, OPPOSITE, "a"))

    metric = build_metric(domain, estimator)
    matching_score, _ = metric(generate_demo(domain, REQUEST, PREFERRED), REQUEST)
    mismatching_score, _ = metric(generate_demo(domain, REQUEST, OPPOSITE), REQUEST)
    prompt = build_seed_prompt(domain, estimator)

    assert matching_score == 1.0
    assert matching_score > mismatching_score
    assert "역할별 파일로 분리" in prompt
    assert "theme 또는" in prompt
    assert "타입을 꼼꼼하게" in prompt
