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
    app.radio(key="run_mode").set_value("무료 데모 (API 없이 규칙 기반)").run()

    app.text_area[0].input("클릭 횟수를 보여주는 버튼을 만들어 주세요.").run()
    app.button(key="start").click().run()
    assert app.session_state["stage"] == "compare"

    for _ in range(8):
        app.button(key="pick_a").click().run()
        assert not app.exception

    assert app.session_state["stage"] == "done"
    # 완주 여부는 문구가 아니라 **산출물**로 본다. 화면 문구는 개편마다
    # 바뀌는데 프롬프트가 나왔는지는 바뀌지 않는 조건이다.
    assert app.code, "결과 화면에 시스템 프롬프트가 없습니다."
    assert app.code[0].value.strip()
    # 제목 순서에 기대지 않는다. 화면을 고칠 때마다 깨진다.
    assert app.code[0].value.strip(), "시스템 프롬프트가 비어 있습니다."


def test_summarization_category_is_still_available() -> None:
    app = AppTest.from_file(APP_PATH, default_timeout=10).run()
    app.selectbox[0].select("문서 요약 (영어)").run()

    assert not app.exception
    assert app.text_area[0].label == "요약할 원문 (영어 뉴스 기사 권장)"


def test_korean_summarization_category_is_available() -> None:
    app = AppTest.from_file(APP_PATH, default_timeout=10).run()
    app.selectbox[0].select("문서 요약 (한국어)").run()

    assert not app.exception
    assert app.text_area[0].label == "요약할 원문 (한국어 뉴스 기사 권장)"


def test_korean_summarization_demo_completes_without_api(monkeypatch) -> None:
    """한국어 요약도 API 없이 결과 화면까지 완주해야 한다.

    demos/summarization_ko.py 가 없으면 engine/demo_generator.py 가
    ValueError를 내므로, 데모 경로가 실제로 연결됐는지 확인하는 테스트다.
    """
    generator_module = importlib.import_module("engine.generator")
    gepa_module = importlib.import_module("optimize.run_gepa")

    def fail_if_called(*args, **kwargs):
        raise AssertionError("무료 데모에서 API 경로를 호출하면 안 됩니다.")

    monkeypatch.setattr(generator_module, "generate", fail_if_called)
    monkeypatch.setattr(gepa_module, "run", fail_if_called)

    app = AppTest.from_file(APP_PATH, default_timeout=30).run()
    app.selectbox[0].select("문서 요약 (한국어)").run()
    app.radio(key="run_mode").set_value("무료 데모 (API 없이 규칙 기반)").run()

    app.text_area[0].input(
        "정부는 15일 수도권 주택 공급을 늘리기 위한 대책을 발표했다. "
        "국토교통부에 따르면 2026년까지 신규 택지 12만 가구가 공급된다. "
        "전문가들은 이번 대책이 제한적인 효과를 낼 것으로 전망했다. "
        "시민단체는 임대주택 비중이 낮다고 비판했다."
    ).run()
    app.button(key="start").click().run()
    assert not app.exception
    assert app.session_state["stage"] == "compare"

    for _ in range(8):
        app.button(key="pick_a").click().run()
        assert not app.exception

    assert app.session_state["stage"] == "done"
    # 완주 여부는 문구가 아니라 **산출물**로 본다. 화면 문구는 개편마다
    # 바뀌는데 프롬프트가 나왔는지는 바뀌지 않는 조건이다.
    assert app.code, "결과 화면에 시스템 프롬프트가 없습니다."
    assert app.code[0].value.strip()

    # 선호가 원시 JSON이 아니라 한국어 라벨로 표시되는지 확인한다.
    rendered = " ".join(item.value for item in app.markdown)
    assert "요약 길이" in rendered
    assert "표현 방식" in rendered


def test_api_failure_degrades_to_demo_instead_of_dead_ending(monkeypatch) -> None:
    """API 호출이 실패하면 막다른 화면이 아니라 데모 모드로 이어져야 한다.

    공개 링크에서 키 만료나 결제 한도로 생성이 실패할 때, 예전 코드는
    st.stop()으로 멈춰 지금까지의 선택이 전부 버려졌다. 처음 보는 사람
    눈에는 고장난 서비스이므로 회귀를 막는다.
    """
    generator_module = importlib.import_module("engine.generator")

    def boom(*args, **kwargs):
        raise RuntimeError("AuthenticationError: invalid api key")

    monkeypatch.setattr(generator_module, "generate", boom)

    app = AppTest.from_file(APP_PATH, default_timeout=30).run()
    # 실행 모드는 건드리지 않는다 - 기본값이 API 모드다.
    app.text_area[0].input("클릭 횟수를 보여주는 버튼을 만들어 주세요.").run()
    app.button(key="start").click().run()

    assert not app.exception
    # API 모드로 시작했지만 실패 후 데모 모드로 내려와 있어야 한다.
    assert app.session_state["demo_mode"] is True
    assert "invalid api key" in app.session_state["api_error"]
    assert app.session_state["stage"] == "compare"
    # 실패 사실을 숨기지 않고 알린다.
    assert any("무료 데모 모드로 전환" in w.value for w in app.warning)

    # 남은 비교를 끝까지 진행할 수 있어야 한다.
    for _ in range(8):
        app.button(key="pick_a").click().run()
        assert not app.exception

    assert app.session_state["stage"] == "done"
    # 완주 여부는 문구가 아니라 **산출물**로 본다. 화면 문구는 개편마다
    # 바뀌는데 프롬프트가 나왔는지는 바뀌지 않는 조건이다.
    assert app.code, "결과 화면에 시스템 프롬프트가 없습니다."
    assert app.code[0].value.strip()


def test_source_input_has_length_cap() -> None:
    """공개 링크 비용 방어: 원문 입력에 길이 상한이 걸려 있어야 한다."""
    app = AppTest.from_file(APP_PATH, default_timeout=10).run()
    assert not app.exception
    assert app.text_area[0].max_chars == 12000
