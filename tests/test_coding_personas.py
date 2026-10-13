"""서로 다른 가상 선택 패턴의 데모 결과를 검증한다. 실제 사용자 평가는 아니다."""

import pytest

import service


REQUEST = "클릭 횟수를 보여 주고 초기화할 수 있는 React 버튼 컴포넌트"
INSTRUCTIONS = {
    "code_structure": {
        "compact": "한 파일 안에",
        "separated": "역할별 파일로 분리",
    },
    "style_management": {
        "direct": "직접 작성하여",
        "theme": "theme 또는",
    },
    "type_detail": {
        "inferred": "타입 추론 중심",
        "explicit": "타입을 꼼꼼하게",
    },
}
PERSONAS = [
    ("간결·직접·추론", "compact", "direct", "inferred"),
    ("분리·테마·명시", "separated", "theme", "explicit"),
    ("간결·테마·명시", "compact", "theme", "explicit"),
    ("분리·직접·추론", "separated", "direct", "inferred"),
    ("구조 미결정·테마·명시", "", "theme", "explicit"),
]


def run_demo(target: dict[str, str], *, revise_first: bool = False):
    state = service.start_session(
        REQUEST, "coding", "domains/coding.yaml", model="unused", demo_mode=True
    )
    shown = []
    if revise_first:
        first = state.pair
        assert first is not None
        axis = next(name for name in target if first.a.combo[name] != first.b.combo[name])
        wrong = "a" if first.a.combo[axis] != target[axis] else "b"
        state = service.submit_choice(state, first.pair_id, wrong)
        state = service.undo_choice(state)
        assert state.pair is not None
        assert (state.pair.a.combo, state.pair.b.combo) == (
            first.a.combo, first.b.combo
        )

    while not state.done:
        pair = state.pair
        assert pair is not None
        differing = [name for name in target if pair.a.combo[name] != pair.b.combo[name]]
        assert len(differing) == 1
        axis = differing[0]
        value = target[axis]
        choice = "tie" if not value else "a" if pair.a.combo[axis] == value else "b"
        shown.append((axis, choice, pair.a.text, pair.b.text))
        state = service.submit_choice(state, pair.pair_id, choice)

    domain, estimator = service.current_estimate(state)
    return state, shown, service.final_combo(domain, estimator), service.final_prompt(
        domain, estimator, language="ko"
    )


@pytest.mark.parametrize("label,structure,style,typing", PERSONAS, ids=[p[0] for p in PERSONAS])
def test_distinct_demo_personas_match_their_final_prompt(label, structure, style, typing):
    target = {
        "code_structure": structure,
        "style_management": style,
        "type_detail": typing,
    }
    state, shown, result, prompt = run_demo(target)

    assert state.demo_mode
    assert len(shown) == 3
    assert {axis for axis, *_ in shown} == set(target)
    assert result == target, label
    for axis, options in INSTRUCTIONS.items():
        for value, phrase in options.items():
            assert (phrase in prompt) == (result[axis] == value), (label, axis, value)

    # 세션 ID는 달라도 같은 요청과 선택 패턴이면 후보와 최종 결과가 같아야 한다.
    _, again, again_result, again_prompt = run_demo(target)
    assert shown == again
    assert result == again_result
    assert prompt == again_prompt


def test_revising_a_wrong_choice_restores_the_intended_preference():
    target = {
        "code_structure": "compact",
        "style_management": "direct",
        "type_detail": "inferred",
    }
    _, _, result, prompt = run_demo(target, revise_first=True)
    assert result == target
    assert INSTRUCTIONS["code_structure"]["compact"] in prompt
    assert INSTRUCTIONS["code_structure"]["separated"] not in prompt
