"""Streamlit 무료 코딩 데모가 API 없이 결과 화면까지 동작하는지 검증."""

import importlib
from pathlib import Path

from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def test_coding_demo_completes_without_api(monkeypatch) -> None:
    generator_module = importlib.import_module("engine.generator")
    gepa_module = importlib.import_module("optimize.run_gepa")

    def fail_if_called(*args, **kwargs):
        raise AssertionError("무료 데모에서 API 경로를 호출하면 안 됩니다.")

    monkeypatch.setattr(generator_module, "generate", fail_if_called)
    monkeypatch.setattr(gepa_module, "run", fail_if_called)

    app = AppTest.from_file(APP_PATH, default_timeout=10).run()
    assert not app.exception
    assert app.selectbox[0].value == "코딩 도움"

    # 기본 실행 모드는 API 모드이므로 무료 데모를 명시적으로 고른다.
    app.radio[0].set_value("무료 데모 (API 없이 규칙 기반)").run()

    app.text_area[0].input("클릭 횟수를 보여주는 버튼을 만들어 주세요.").run()
    app.button[0].click().run()
    assert app.session_state["stage"] == "compare"

    for _ in range(8):
        app.button[0].click().run()
        assert not app.exception

    assert app.session_state["stage"] == "done"
    assert app.success[0].value == "선택이 모두 끝났습니다."
    assert "시스템 프롬프트" in app.subheader[1].value


def test_summarization_category_is_still_available() -> None:
    app = AppTest.from_file(APP_PATH, default_timeout=10).run()
    app.selectbox[0].select("문서 요약").run()

    assert not app.exception
    assert app.text_area[0].label == "요약할 원문 (영어 뉴스 기사 권장)"
