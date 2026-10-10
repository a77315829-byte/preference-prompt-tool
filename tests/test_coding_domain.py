"""코딩 도메인의 선택·평가·프롬프트 조립 검증."""

import itertools

import api_server
import service
from checks.coding import candidate_quality_issues, count_files, count_theme_signals, count_type_signals
from demos.coding import demo_scenario
from engine.demo_generator import generate_demo
from engine.domain_loader import load_domain
from engine.estimator import Comparison, Estimator
from engine.generator import build_prompt
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


def test_single_unnamed_code_block_counts_as_one_file() -> None:
    output = "```tsx\nexport function Example() { return <div />; }\n```"
    assert count_files(output) == 1


def test_live_quality_rejects_extra_entrypoint_and_inferred_type_annotations() -> None:
    combo = {
        "code_structure": "separated",
        "style_management": "direct",
        "type_detail": "inferred",
    }
    output = (
        "index.tsx\n```tsx\nexport const App: React.FC = () => <div />;\n```\n"
        "App.css\n```css\ndiv { color: red; }\n```"
    )
    issues = candidate_quality_issues(output, combo, REQUEST)
    assert any("타입 추론" in issue for issue in issues)
    assert any("실행 진입점" in issue for issue in issues)


def test_live_quality_rejects_extra_app_but_allows_necessary_event_type() -> None:
    combo = {
        "code_structure": "separated",
        "style_management": "direct",
        "type_detail": "inferred",
    }
    output = (
        "App.tsx\n```tsx\nexport const App = () => <div />;\n```\n"
        "Search.tsx\n```tsx\nexport const Search = () => "
        "<input onChange={(event: React.ChangeEvent<HTMLInputElement>) => {}} />;\n```\n"
        "Search.css\n```css\ninput { color: red; }\n```"
    )
    issues = candidate_quality_issues(output, combo, REQUEST)
    assert any("App 래퍼" in issue for issue in issues)
    assert not any("타입 추론" in issue for issue in issues)


def test_live_quality_requires_type_for_empty_array_state() -> None:
    combo = {"code_structure": "compact", "style_management": "direct", "type_detail": "inferred"}
    bad = "```tsx\nimport { useState } from 'react';\nexport const Todos = () => { const [items, setItems] = useState([]); return <div />; };\n```"
    good = bad.replace("useState([])", "useState<string[]>([])")
    assert any("never[]" in issue for issue in candidate_quality_issues(bad, combo))
    assert not any("타입 추론" in issue or "never[]" in issue for issue in candidate_quality_issues(good, combo))


def test_live_quality_rejects_redundant_primitive_state_type() -> None:
    combo = {"code_structure": "separated", "style_management": "direct", "type_detail": "inferred"}
    output = (
        "CounterButton.tsx\n```tsx\nimport { useState } from 'react';\n"
        "export function CounterButton() { const [count, setCount] = useState<number>(0); "
        "return <button onClick={() => setCount(count + 1)}>{count}</button>; }\n```\n"
        "CounterButton.css\n```css\nbutton { color: blue; }\n```"
    )
    issues = candidate_quality_issues(output, combo, REQUEST)
    assert any("타입 추론" in issue for issue in issues)
    assert not any("타입 추론" in issue for issue in candidate_quality_issues(
        output.replace("useState<number>(0)", "useState(0)"), combo, REQUEST
    ))


def test_live_quality_keeps_explicit_button_text_inside_button() -> None:
    combo = {"code_structure": "compact", "style_management": "direct", "type_detail": "inferred"}
    source = (
        "카운터를 만들어 주세요. 버튼에 보이는 문구는 처음에 정확히 "
        "클릭 횟수: 0이고, 클릭 후에는 숫자만 바뀌어야 합니다."
    )
    wrong = "```tsx\nexport function Counter() { return <div><p>클릭 횟수: {0}</p><button>증가</button></div>; }\n```"
    right = "```tsx\nexport function Counter() { return <button>클릭 횟수: {0}</button>; }\n```"
    assert any("버튼 문구 위반" in issue for issue in candidate_quality_issues(wrong, combo, source))
    assert not any("버튼 문구 위반" in issue for issue in candidate_quality_issues(right, combo, source))


def test_live_quality_allows_necessary_props_types_in_inferred_style() -> None:
    combo = {"code_structure": "compact", "style_management": "direct", "type_detail": "inferred"}
    output = "```tsx\ninterface Item { id: number; title: string; done: boolean }\ninterface Props { item: Item; onToggle: (id: number) => void }\nexport function Row({ item, onToggle }: Props) { return <button onClick={() => onToggle(item.id)}>{item.title}</button>; }\n```"
    assert not candidate_quality_issues(output, combo)


def _combo_for_prompt(domain, source_text: str, prompt: str) -> dict[str, str]:
    for values in itertools.product(*([value.value for value in axis.values] for axis in domain.axes)):
        combo = dict(zip((axis.name for axis in domain.axes), values))
        if prompt.startswith(build_prompt(domain, combo, source=source_text)):
            return combo
    raise AssertionError("생성 프롬프트와 일치하는 코딩 스타일이 없습니다")


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


def test_demo_session_exposes_actual_comparison_task() -> None:
    from demos.coding_dataset import select_coding_task

    for request in ("확인 모달", "예약 달력"):
        state = service.start_session(
            request, "coding", "domains/coding.yaml", model="unused", demo_mode=True
        )
        payload = api_server._state_payload(state)
        expected = select_coding_task(request, state.answered)["request"]
        assert payload["coding_demo_task"] == expected
        assert expected in payload["pair"]["a"]["text"]
        assert expected in payload["pair"]["b"]["text"]
        assert payload["pair"]["a"]["text"]


def test_live_coding_pair_uses_the_user_request_for_both_candidates(monkeypatch) -> None:
    request = "예약 날짜를 고르는 달력 컴포넌트를 만들어 주세요."
    calls = []

    def fake_generate(domain, source_text, combo, model):
        calls.append(("first", source_text, combo, model))
        return generate_demo(domain, source_text, combo)

    def fake_second(prompt, source_text, model):
        calls.append(("second", source_text, prompt, model))
        domain = load_domain("domains/coding.yaml")
        return generate_demo(domain, source_text, _combo_for_prompt(domain, source_text, prompt))

    monkeypatch.setattr(service.generator, "generate", fake_generate)
    monkeypatch.setattr(service.generator, "generate_with_prompt", fake_second)
    state = service.start_session(
        request, "coding", "domains/coding.yaml", model="test-model", demo_mode=False
    )

    assert calls[0][0:2] == ("first", request)
    assert calls[0][3] == "test-model"
    assert calls[1][0:2] == ("second", request)
    assert "첫 번째 구현" in calls[1][2]
    assert state.pair.a.text in calls[1][2]
    assert state.pair.a.text
    assert state.pair.b.text
    assert state.pair.a.combo != state.pair.b.combo
    assert api_server._state_payload(state)["demo_mode"] is False


def test_live_coding_candidate_is_repaired_once_before_display(monkeypatch) -> None:
    domain = load_domain("domains/coding.yaml")
    generated = []
    repaired = []

    def fake_generate(domain, source_text, combo, model):
        generated.append(combo)
        return "```tsx\nexport const Empty = () => null;\n```"

    def fake_followup(prompt, source_text, model):
        combo = _combo_for_prompt(domain, source_text, prompt)
        if "수정할 초안" in prompt:
            repaired.append((source_text, model))
        return generate_demo(domain, source_text, combo)

    monkeypatch.setattr(service.generator, "generate", fake_generate)
    monkeypatch.setattr(service.generator, "generate_with_prompt", fake_followup)
    state = service.start_session(
        REQUEST, "coding", "domains/coding.yaml", model="test-model", demo_mode=False
    )

    assert len(repaired) == 1
    assert not candidate_quality_issues(state.pair.a.text, state.pair.a.combo)
    assert not candidate_quality_issues(state.pair.b.text, state.pair.b.combo)


def test_live_coding_candidate_that_still_violates_style_is_rejected(monkeypatch) -> None:
    monkeypatch.setattr(
        service.generator, "generate", lambda *args, **kwargs: "코드 없음"
    )
    monkeypatch.setattr(
        service.generator, "generate_with_prompt", lambda *args, **kwargs: "코드 없음"
    )
    import pytest

    with pytest.raises(RuntimeError, match="스타일 검사를 통과하지"):
        service.start_session(
            REQUEST, "coding", "domains/coding.yaml", model="test-model", demo_mode=False
        )


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


def test_coding_session_choices_reach_the_final_prompt() -> None:
    state = service.start_session(
        REQUEST, "coding", "domains/coding.yaml", model="unused", demo_mode=True
    )
    while not state.done:
        pair = state.pair
        assert pair is not None
        winner = "a" if _matches(pair.a.combo, PREFERRED) > _matches(pair.b.combo, PREFERRED) else "b"
        state = service.submit_choice(state, pair.pair_id, winner)

    domain, estimator = service.current_estimate(state)
    assert service.final_combo(domain, estimator) == PREFERRED
    prompt = service.final_prompt(domain, estimator, language="ko")
    assert "역할별 파일로 분리" in prompt
    assert "theme 또는" in prompt
    assert "타입을 꼼꼼하게" in prompt
    assert "한 파일 안에" not in prompt
    assert "직접 작성하여" not in prompt


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
