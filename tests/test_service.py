"""순수 레이어를 검사한다. Streamlit 없이 돈다.

이 층이 나중에 FastAPI 로 그대로 옮겨갈 자리이므로, **UI 가 없어도
비교 루프가 완주되는지**와 **상태가 직렬화되는지**를 고정한다.
데모 모드를 쓰므로 API 호출이 없다.
"""

from __future__ import annotations

import dataclasses
import json

import pytest

import service

SOURCE = "정부는 오늘 새 정책을 발표했다. " * 40
DOMAIN = "domains/summarization_ko.yaml"


def _start(**kwargs) -> service.SessionState:
    return service.start_session(
        SOURCE, domain_key="summarization_ko", domain_path=DOMAIN,
        model="openai/gpt-4.1-mini", demo_mode=True, **kwargs,
    )


def test_does_not_import_streamlit() -> None:
    """UI 가 무엇이든 상관없어야 한다. 이게 이 파일의 존재 이유다."""
    import sys

    sys.modules.pop("streamlit", None)
    import importlib

    importlib.reload(service)
    assert "streamlit" not in sys.modules


def test_completes_the_loop_without_api() -> None:
    state = _start()
    while not state.done:
        state = service.submit_choice(state, state.pair.pair_id, "a")
    assert state.answered == state.total_rounds
    assert state.pair is None


def test_state_is_serialisable() -> None:
    """FastAPI 세션 저장소에 그대로 넣을 수 있어야 한다. 엔진 객체를
    담으면 여기서 깨진다."""
    state = _start()
    state = service.submit_choice(state, state.pair.pair_id, "b")
    payload = json.dumps(dataclasses.asdict(state))
    assert json.loads(payload)["domain_key"] == "summarization_ko"


def test_replaying_history_reproduces_the_same_next_pair() -> None:
    """선택기는 내부 RNG 를 호출마다 진행시킨다. 이력 재생으로 같은 쌍이
    나와야 상태를 순수 데이터로 둘 수 있다."""
    state = _start()
    first = service.submit_choice(state, state.pair.pair_id, "a")

    # 같은 이력을 가진 새 상태를 만들어 재생하면 같은 조합이 나와야 한다.
    clone = dataclasses.replace(first, pair=None)
    _, estimator, selector = service._rebuild(clone)
    combo_a, combo_b = selector.next_pair(estimator)
    assert (combo_a, combo_b) == (first.pair.a.combo, first.pair.b.combo)


def test_stale_pair_id_is_rejected() -> None:
    """중복 클릭이나 뒤로 가기로 지난 선택이 늦게 오면 받으면 안 된다."""
    state = _start()
    with pytest.raises(service.StaleChoiceError):
        service.submit_choice(state, "지난쌍", "a")


def test_choice_after_the_session_ends_is_rejected() -> None:
    state = _start()
    while not state.done:
        state = service.submit_choice(state, state.pair.pair_id, "a")
    with pytest.raises(service.StaleChoiceError):
        service.submit_choice(state, "아무거나", "a")


def test_invalid_choice_is_rejected() -> None:
    state = _start()
    with pytest.raises(ValueError):
        service.submit_choice(state, state.pair.pair_id, "c")


def test_gauge_counts_only_comparisons_where_the_axis_differed() -> None:
    """게이지 값이 "갈린 비교 수"라는 정의를 고정한다.

    확신도를 쓰지 않는 이유는 실측이다 - 3값 축은 24회까지 0.06 에
    머무는데 선호는 9/9 복원한다. 차오르는 바에 그 값을 걸면 움직이지
    않고, 맞힌 사용자에게 6% 라고 말한다.
    """
    state = _start()
    while not state.done:
        state = service.submit_choice(state, state.pair.pair_id, "a")

    for axis in state.axes:
        manual = sum(
            1
            for combo_a, combo_b, _ in state.history
            if combo_a.get(axis.name) != combo_b.get(axis.name)
        )
        assert axis.discriminated == manual
        assert 0.0 <= axis.fill <= 1.0
    # 선택기가 축을 번갈아 고르므로 합이 라운드 수를 넘지 않는다.
    assert sum(a.discriminated for a in state.axes) <= state.total_rounds


def test_gauge_skips_freeform_axes() -> None:
    """요약의 topic 은 자유 키워드라 추정값·확신도 모델에 맞지 않는다.
    그래서 게이지는 3개가 아니라 2개다 - 화면이 개수를 하드코딩하면 안 된다."""
    state = _start()
    assert [axis.name for axis in state.axes] == ["length", "extractiveness"]


def test_prefetch_is_a_no_op_in_demo_mode() -> None:
    """데모 모드는 API 를 쓰지 않으므로 미리 만들 것이 없다."""
    state = _start()
    service.prefetch_branches(state)  # 예외 없이 끝나야 한다


def test_prefetch_does_not_mutate_the_state() -> None:
    """스레드에서 부를 수 있어야 한다. 상태를 건드리면 경합이 생긴다."""
    state = _start()
    before = dataclasses.asdict(state)
    service.prefetch_branches(state)
    assert dataclasses.asdict(state) == before
