"""결과 화면의 "기본 프롬프트 vs 내 프롬프트" 비교 검증.

이 앱의 산출물은 프롬프트 문자열이라, 이 비교가 없으면 사용자는 앱 밖으로
나가야 개인화가 먹혔는지 알 수 있다. API는 호출하지 않고 생성 함수를
대체해서 UI 경로만 검사한다.
"""

import importlib
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"
DEMO_MODE = "무료 데모 (API 없이 규칙 기반)"
TRIAL_BUTTON = "두 프롬프트로 생성해 비교"
SOURCE = "클릭 횟수를 보여주는 버튼을 만들어 주세요."


def _button(app, label: str):
    for button in app.button:
        if button.label == label:
            return button
    raise AssertionError(f"버튼을 못 찾음: {label!r}. 있는 것: {[b.label for b in app.button]}")


def _has_button(app, label: str) -> bool:
    return any(b.label == label for b in app.button)


def _finish_run(app, *, demo: bool) -> None:
    if demo:
        app.radio[0].set_value(DEMO_MODE).run()
    app.text_area[0].input(SOURCE).run()
    app.button[0].click().run()
    for _ in range(8):
        app.button[0].click().run()
        assert not app.exception
    assert app.session_state["stage"] == "done"


def test_trial_is_offered_in_api_mode(monkeypatch) -> None:
    generator = importlib.import_module("engine.generator")
    monkeypatch.setattr(generator, "generate", lambda *a, **k: "생성된 후보")

    app = AppTest.from_file(APP_PATH, default_timeout=60).run()
    _finish_run(app, demo=False)

    assert any("새 원문에 적용" in s.value for s in app.subheader)
    assert _has_button(app, TRIAL_BUTTON)


def test_trial_is_gated_in_demo_mode(monkeypatch) -> None:
    """데모 모드는 모델을 호출하지 않으므로 비교를 제공할 수 없다.
    조용히 감추지 않고 왜 안 되는지 알려야 한다."""
    generator = importlib.import_module("engine.generator")
    monkeypatch.setattr(
        generator, "generate",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("데모에서 API 호출 금지")),
    )

    app = AppTest.from_file(APP_PATH, default_timeout=60).run()
    _finish_run(app, demo=True)

    assert not _has_button(app, TRIAL_BUTTON)
    captions = " ".join(c.value for c in app.caption)
    assert "무료 데모 모드에서는 이 비교를 쓸 수 없습니다" in captions


def test_trial_shows_both_outputs_side_by_side(monkeypatch) -> None:
    generator = importlib.import_module("engine.generator")
    monkeypatch.setattr(generator, "generate", lambda *a, **k: "생성된 후보")

    seen_prompts = []

    # 시그니처를 실제와 맞춘다. engine 쪽에 인자가 늘었을 때 대역 함수가
    # TypeError 를 내고, app.py 가 그걸 잡아 데모로 강등시켜 버려서 이
    # 테스트가 "호출된 프롬프트 0개"로 실패했다. **kwargs 로 열어둔다.
    def fake_with_prompt(prompt, source_text, model, cache_dir=None, **kwargs):
        seen_prompts.append(prompt)
        return f"[{'기본' if len(seen_prompts) == 1 else '개인'}] {source_text[:10]}"

    monkeypatch.setattr(generator, "generate_with_prompt", fake_with_prompt)

    app = AppTest.from_file(APP_PATH, default_timeout=60).run()
    _finish_run(app, demo=False)

    app.text_area[0].input("새로운 요청 사항입니다.").run()
    _button(app, TRIAL_BUTTON).click().run()
    assert not app.exception

    assert len(seen_prompts) == 2, seen_prompts
    # 기준선은 축 지시문이 빠진 task_description 뿐이어야 한다.
    baseline, personal = seen_prompts
    assert len(baseline) < len(personal), (baseline, personal)
    assert baseline in personal

    body = " ".join(t.value for t in app.markdown) + " ".join(str(t.value) for t in app.text)
    rendered = body + " ".join(c.value for c in app.caption)
    assert "개인화 없음" in rendered
    assert "8회 선택으로 만든 프롬프트" in rendered


def test_trial_respects_session_cap(monkeypatch) -> None:
    generator = importlib.import_module("engine.generator")
    monkeypatch.setattr(generator, "generate", lambda *a, **k: "생성된 후보")
    monkeypatch.setattr(
        generator, "generate_with_prompt",
        lambda prompt, source_text, model, cache_dir=None, **kwargs: "결과",
    )

    app = AppTest.from_file(APP_PATH, default_timeout=90).run()
    _finish_run(app, demo=False)

    assert "trials_used" not in app.session_state

    for i in range(3):
        app.text_area[0].input(f"원문 {i}").run()
        _button(app, TRIAL_BUTTON).click().run()
        assert not app.exception

    assert app.session_state["trials_used"] == 3
    assert not _has_button(app, TRIAL_BUTTON)
    captions = " ".join(c.value for c in app.caption)
    assert "세션당" in captions


# --- 실사용자 의견 수집 ----------------------------------------------------

YES_BUTTON = "네, 맞아요"
NO_BUTTON = "아니요, 아쉬워요"


def test_feedback_form_is_offered_after_a_run(monkeypatch) -> None:
    generator = importlib.import_module("engine.generator")
    monkeypatch.setattr(generator, "generate", lambda *a, **k: "생성된 후보")

    app = AppTest.from_file(APP_PATH, default_timeout=60).run()
    _finish_run(app, demo=False)

    assert any("취향에 맞나요" in s.value for s in app.subheader)
    assert _has_button(app, YES_BUTTON)
    assert _has_button(app, NO_BUTTON)


def test_answering_records_and_thanks(monkeypatch) -> None:
    generator = importlib.import_module("engine.generator")
    monkeypatch.setattr(generator, "generate", lambda *a, **k: "생성된 후보")

    app = AppTest.from_file(APP_PATH, default_timeout=60).run()
    _finish_run(app, demo=False)

    _button(app, YES_BUTTON).click().run()
    assert not app.exception
    assert app.session_state["feedback_sent"] is True
    # 두 번 답하게 두면 표본이 한 사람에게 치우친다.
    assert not _has_button(app, YES_BUTTON)
    assert any("의견 감사합니다" in s.value for s in app.success)


def test_feedback_is_offered_in_demo_mode_too(monkeypatch) -> None:
    """데모 모드 응답도 모아둔다. 다만 기록에 모드가 남아 나중에 분리된다."""
    generator = importlib.import_module("engine.generator")
    monkeypatch.setattr(
        generator, "generate",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("데모에서 API 호출 금지")),
    )

    app = AppTest.from_file(APP_PATH, default_timeout=60).run()
    _finish_run(app, demo=True)
    assert _has_button(app, YES_BUTTON)
