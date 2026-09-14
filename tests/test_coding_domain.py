"""코딩 도메인의 선택·평가·프롬프트 조립 검증."""

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
