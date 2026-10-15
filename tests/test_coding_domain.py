"""코딩 도메인의 선택·평가·프롬프트 조립 검증."""

import itertools

import api_server
import service
from checks.coding import (
    candidate_quality_issues, code_module_counts, count_files, count_theme_signals,
    count_type_signals, inline_pseudo_conflicts, pair_quality_issues,
)
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


def test_pair_quality_catches_extra_logic_module_but_allows_theme_css() -> None:
    first = (
        "ConfirmDialog.tsx\n```tsx\nimport './ConfirmDialog.css';\n"
        "export function ConfirmDialog() { return <button>삭제하기</button>; }\n```\n"
        "ConfirmDialog.css\n```css\nbutton { color: blue; }\n```"
    )
    theme_only = first + "\ntheme.css\n```css\n:root { --accent: blue; }\n```"
    extra_logic = theme_only + "\nuseConfirm.ts\n```ts\nexport const useConfirm = () => true;\n```"
    direct = {"code_structure": "separated", "style_management": "direct"}
    theme = {"code_structure": "separated", "style_management": "theme"}

    assert code_module_counts(first) == (1, 0)
    assert pair_quality_issues(first, theme_only, direct, theme) == []
    assert any("코드 구조" in issue for issue in pair_quality_issues(first, extra_logic, direct, theme))
    assert pair_quality_issues(first, extra_logic, {**direct, "code_structure": "compact"}, theme) == []


def test_pair_quality_catches_extra_interaction_in_structure_comparison() -> None:
    split = (
        "Counter.tsx\n```tsx\nimport { useState } from 'react';\n"
        "export function Counter() { const [n, setN] = useState(0); "
        "return <button onClick={() => setN(n + 1)}>{n}</button>; }\n```\n"
        "Counter.css\n```css\nbutton:hover { color: blue; }\n```"
    )
    compact = (
        "Counter.tsx\n```tsx\nimport { useState } from 'react';\n"
        "export function Counter() { const [n, setN] = useState(0); "
        "return <><style>{`button:hover { color: blue; }`}</style>"
        "<button onClick={() => setN(n + 1)}>{n}</button></>; }\n```"
    )
    drifted = compact.replace(
        "const [n, setN] = useState(0);",
        "const [n, setN] = useState(0); const [hover, setHover] = useState(false);",
    ).replace("button:hover", "button").replace(
        "<button onClick", "<button onMouseEnter={() => setHover(true)} onClick"
    )
    separated = {"code_structure": "separated"}
    one_file = {"code_structure": "compact"}

    assert pair_quality_issues(split, compact, separated, one_file) == []
    issues = pair_quality_issues(split, drifted, separated, one_file)
    assert len(issues) == 1
    assert "공통 상호작용 위반" in issues[0]
    assert "hook:useState" in issues[0]
    assert "handler:onMouseEnter" in issues[0]


def test_live_pair_repairs_non_target_structure_drift(monkeypatch) -> None:
    domain = load_domain("domains/coding.yaml")
    direct = {"code_structure": "separated", "style_management": "direct", "type_detail": "explicit"}
    theme = {**direct, "style_management": "theme"}
    first = generate_demo(domain, REQUEST, direct)
    second = generate_demo(domain, REQUEST, theme)
    extra = "\nuseCounter.ts\n```ts\nexport const useCounter = () => 0;\n```"
    calls = []

    def fake_generate(prompt, source_text, model):
        calls.append(prompt)
        if len(calls) == 1:
            return first
        if len(calls) == 2:
            return second + extra
        return second

    monkeypatch.setattr(service.generator, "generate_with_prompt", fake_generate)
    state = service.SessionState(
        session_id="pair-check", domain_key="coding", domain_path="domains/coding.yaml",
        source_text=REQUEST, model="test-model", demo_mode=False,
    )
    pair = service._generate_pair(state, domain, direct, theme)

    assert len(calls) == 3
    assert "바꿀 축은 style_management뿐" in calls[1]
    assert "공통 코드 구조 위반" in calls[2]
    assert "구조를 맞출 기준 A" in calls[2]
    assert pair.a.text == first and pair.b.text == second


def test_live_pair_repairs_extra_hover_state_when_structure_changes(monkeypatch) -> None:
    domain = load_domain("domains/coding.yaml")
    split = {"code_structure": "separated", "style_management": "direct", "type_detail": "explicit"}
    compact = {**split, "code_structure": "compact"}
    first = generate_demo(domain, REQUEST, split)
    second = generate_demo(domain, REQUEST, compact)
    drifted = second.replace(
        "const [count, setCount] = useState<number>(initialCount);",
        "const [count, setCount] = useState<number>(initialCount);\n"
        "  const [hovered, setHovered] = useState(false);",
    ).replace("onClick={increment}", "onMouseEnter={() => setHovered(true)} onClick={increment}")
    calls = []

    def fake_generate(prompt, source_text, model):
        calls.append(prompt)
        return (first, drifted, second)[len(calls) - 1]

    monkeypatch.setattr(service.generator, "generate_with_prompt", fake_generate)
    state = service.SessionState(
        session_id="interaction-check", domain_key="coding", domain_path="domains/coding.yaml",
        source_text=REQUEST, model="test-model", demo_mode=False,
    )
    pair = service._generate_pair(state, domain, split, compact)

    assert len(calls) == 3
    assert "공통 상호작용 위반" in calls[2]
    assert "hook:useState" in calls[2]
    assert pair.a.text == first and pair.b.text == second


def test_inline_style_cannot_hide_hover_background() -> None:
    output = (
        "```tsx\nexport const Button = () => <button className=\"action\" "
        "style={{ background: '#fff' }}>Go</button>;\n```"
        "```css\n.action:hover { background: #eee; }\n```"
    )
    combo = {"code_structure": "compact", "style_management": "direct", "type_detail": "inferred"}

    assert inline_pseudo_conflicts(output) == [".action:hover의 background"]
    assert any("호버/포커스 스타일 위반" in issue for issue in candidate_quality_issues(output, combo))


def test_inline_style_can_keep_unrelated_property_with_hover() -> None:
    output = (
        "```tsx\nexport const Button = () => <button className=\"action\" "
        "style={{ padding: 8 }}>Go</button>;\n```"
        "```css\n.action { background: #fff; } .action:hover { background: #eee; }\n```"
    )

    assert inline_pseudo_conflicts(output) == []


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


def test_live_quality_rejects_global_jsx_namespace_for_react_19() -> None:
    combo = {"code_structure": "compact", "style_management": "direct", "type_detail": "inferred"}
    bad = "```tsx\nexport function Counter(): JSX.Element { return <button>0</button>; }\n```"
    good = bad.replace("JSX.Element", "React.JSX.Element")
    inferred = bad.replace(": JSX.Element", "")

    assert any("전역 JSX" in issue for issue in candidate_quality_issues(bad, combo))
    assert not any("전역 JSX" in issue for issue in candidate_quality_issues(good, combo))
    assert not any("전역 JSX" in issue for issue in candidate_quality_issues(inferred, combo))


def test_live_quality_accepts_imported_jsx_only_in_its_own_module() -> None:
    combo = {"code_structure": "compact", "style_management": "direct", "type_detail": "inferred"}
    for declaration in (
        "import type { JSX } from 'react';",
        "import { useState, type JSX } from 'react';",
    ):
        imported = f"```tsx\n{declaration}\nexport function Counter(): JSX.Element {{ return <button>0</button>; }}\n```"
        assert not any("전역 JSX" in issue for issue in candidate_quality_issues(imported, combo))
        other_module = imported + "\n```tsx\nexport function Other(): JSX.Element { return <div />; }\n```"
        assert any("전역 JSX" in issue for issue in candidate_quality_issues(other_module, combo))
    aliased = "```tsx\nimport type { JSX as ReactJSX } from 'react';\nexport function Counter(): JSX.Element { return <div />; }\n```"
    assert any("전역 JSX" in issue for issue in candidate_quality_issues(aliased, combo))


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

    def fake_generate(prompt, source_text, model):
        calls.append((prompt, source_text, model))
        domain = load_domain("domains/coding.yaml")
        return generate_demo(domain, source_text, _combo_for_prompt(domain, source_text, prompt))

    monkeypatch.setattr(service.generator, "generate_with_prompt", fake_generate)
    state = service.start_session(
        request, "coding", "domains/coding.yaml", model="test-model", demo_mode=False
    )

    assert len(calls) == 2
    assert all(source == request and model == "test-model" for _, source, model in calls)
    assert all("A/B 공통 기능 계약" in prompt for prompt, _, _ in calls)
    assert all("사용자 메시지를 두 후보 모두의 동일한 기능 명세" in prompt for prompt, _, _ in calls)
    assert all("React 19·TypeScript 5" in prompt for prompt, _, _ in calls)
    assert all("포커스/호버 상태까지" in prompt for prompt, _, _ in calls)
    assert "첫 번째 구현" not in calls[0][0]
    assert "첫 번째 구현" in calls[1][0]
    assert "접근성 속성과 스타일 값도" in calls[1][0]
    assert state.pair.a.text in calls[1][0]
    assert state.pair.a.text
    assert state.pair.b.text
    assert state.pair.a.combo != state.pair.b.combo
    assert api_server._state_payload(state)["demo_mode"] is False


def test_live_coding_candidate_is_repaired_once_before_display(monkeypatch) -> None:
    domain = load_domain("domains/coding.yaml")
    repaired = []

    def fake_followup(prompt, source_text, model):
        combo = _combo_for_prompt(domain, source_text, prompt)
        if "수정할 초안" in prompt:
            repaired.append((prompt, source_text, model))
            return generate_demo(domain, source_text, combo)
        if not repaired:
            return "```tsx\nexport const Empty = () => null;\n```"
        return generate_demo(domain, source_text, combo)

    monkeypatch.setattr(service.generator, "generate_with_prompt", fake_followup)
    state = service.start_session(
        REQUEST, "coding", "domains/coding.yaml", model="test-model", demo_mode=False
    )

    assert len(repaired) == 1
    assert "A/B 공통 기능 계약" in repaired[0][0]
    assert repaired[0][1:] == (REQUEST, "test-model")
    assert not candidate_quality_issues(state.pair.a.text, state.pair.a.combo)
    assert not candidate_quality_issues(state.pair.b.text, state.pair.b.combo)


def test_explicit_public_return_type_is_required_even_with_other_type_signals() -> None:
    domain = load_domain("domains/coding.yaml")
    valid = generate_demo(domain, REQUEST, PREFERRED)
    missing = valid.replace(": ReactElement {", " {", 1)

    assert missing != valid
    assert not candidate_quality_issues(valid, PREFERRED, REQUEST)
    assert count_type_signals(missing) >= 5
    assert any("반환 타입이 없다" in issue for issue in candidate_quality_issues(missing, PREFERRED, REQUEST))
    # 추론 중심 선택에는 반환 타입을 강제하지 않는다.
    assert not any("반환 타입이 없다" in issue for issue in candidate_quality_issues(missing, OPPOSITE, REQUEST))


def test_missing_public_return_type_is_repaired_before_pair_is_displayed(monkeypatch) -> None:
    domain = load_domain("domains/coding.yaml")
    state = service.start_session(REQUEST, "coding", "domains/coding.yaml", model="test-model", demo_mode=True)
    state.demo_mode = False
    state.model = "test-model"
    state.coding_escalation_model = None
    calls = []

    def fake_generate(prompt, source_text, model):
        calls.append(prompt)
        combo = _combo_for_prompt(domain, source_text, prompt)
        output = generate_demo(domain, source_text, combo)
        return output.replace(": ReactElement {", " {", 1) if len(calls) == 1 else output

    monkeypatch.setattr(service.generator, "generate_with_prompt", fake_generate)
    pair = service._generate_pair(state, domain, PREFERRED, OPPOSITE)

    assert len(calls) == 3  # A 초안 → A 수정 → B 생성
    assert "반환 타입이 없다" in calls[1]
    assert "수정할 초안" in calls[1]
    assert not candidate_quality_issues(pair.a.text, PREFERRED, REQUEST)
    assert not candidate_quality_issues(pair.b.text, OPPOSITE, REQUEST)


def test_missing_public_return_type_still_rejected_after_repair(monkeypatch) -> None:
    import pytest

    domain = load_domain("domains/coding.yaml")
    state = service.start_session(REQUEST, "coding", "domains/coding.yaml", model="test-model", demo_mode=True)
    state.demo_mode = False
    state.model = "test-model"
    state.coding_escalation_model = None
    calls = []

    def fake_generate(prompt, source_text, model):
        calls.append(prompt)
        return generate_demo(domain, source_text, PREFERRED).replace(": ReactElement {", " {", 1)

    monkeypatch.setattr(service.generator, "generate_with_prompt", fake_generate)
    with pytest.raises(service.CodingCandidateQualityError) as error:
        service._generate_pair(state, domain, PREFERRED, OPPOSITE)
    assert len(calls) == 2
    assert any("반환 타입이 없다" in issue for issue in error.value.issues)


def test_live_coding_candidate_that_still_violates_style_is_rejected(monkeypatch) -> None:
    monkeypatch.setattr(
        service.generator, "generate_with_prompt", lambda *args, **kwargs: "코드 없음"
    )
    import pytest

    with pytest.raises(service.CodingCandidateQualityError, match="스타일 검사를 통과하지") as error:
        service.start_session(
            REQUEST, "coding", "domains/coding.yaml", model="test-model", demo_mode=False
        )
    assert error.value.candidate == "A"
    assert error.value.issues
    assert "코드 없음" not in str(error.value)


def test_live_coding_escalates_only_after_primary_repair_fails(monkeypatch) -> None:
    domain = load_domain("domains/coding.yaml")
    calls = []

    def fake_generate(prompt, source_text, model):
        calls.append((prompt, source_text, model))
        if len(calls) <= 2:
            return "코드 없음"
        combo = _combo_for_prompt(domain, source_text, prompt)
        return generate_demo(domain, source_text, combo)

    monkeypatch.setattr(service.generator, "generate_with_prompt", fake_generate)
    state = service.start_session(
        REQUEST, "coding", "domains/coding.yaml", model="openai/gpt-6-luna",
        coding_escalation_model="openai/gpt-6.1-sol", demo_mode=False,
    )

    assert [model for _, _, model in calls] == [
        "openai/gpt-6-luna", "openai/gpt-6-luna",
        "openai/gpt-6.1-sol", "openai/gpt-6-luna",
    ]
    assert all(source == REQUEST for _, source, _ in calls)
    assert "실패한 수정본" in calls[2][0]
    assert "A/B 공통 기능 계약" in calls[2][0]
    assert not candidate_quality_issues(state.pair.a.text, state.pair.a.combo, REQUEST)
    assert not candidate_quality_issues(state.pair.b.text, state.pair.b.combo, REQUEST)


def test_live_coding_escalation_stops_after_one_attempt(monkeypatch) -> None:
    import pytest

    models = []

    def fake_generate(prompt, source_text, model):
        models.append(model)
        return "코드 없음"

    monkeypatch.setattr(service.generator, "generate_with_prompt", fake_generate)
    with pytest.raises(service.CodingCandidateQualityError) as error:
        service.start_session(
            REQUEST, "coding", "domains/coding.yaml", model="openai/gpt-6-luna",
            coding_escalation_model="openai/gpt-6.1-sol", demo_mode=False,
        )
    assert error.value.candidate == "A"
    assert models == ["openai/gpt-6-luna", "openai/gpt-6-luna", "openai/gpt-6.1-sol"]


def test_live_coding_api_error_does_not_escalate(monkeypatch) -> None:
    import pytest

    models = []

    def fake_generate(prompt, source_text, model):
        models.append(model)
        raise RuntimeError("API 호출 실패")

    monkeypatch.setattr(service.generator, "generate_with_prompt", fake_generate)
    with pytest.raises(RuntimeError, match="API 호출 실패"):
        service.start_session(
            REQUEST, "coding", "domains/coding.yaml", model="openai/gpt-6-luna",
            coding_escalation_model="openai/gpt-6.1-sol", demo_mode=False,
        )
    assert models == ["openai/gpt-6-luna"]


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
