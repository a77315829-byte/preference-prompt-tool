"""앱에 노출된 모든 카테고리가 데모 모드로 완주하는지 검증.

카테고리를 하나 추가할 때마다 사람이 손으로 눌러보는 대신 여기서 막는다.
demos/generic.py fallback 덕분에 전용 데모 생성기가 없는 도메인도 돌아야
한다 - 그게 "YAML만 추가하면 앱까지 붙는다"는 주장의 실체다.

API 키가 없어도 돌아간다. 데모 모드는 모델을 호출하지 않는다.
"""

import importlib
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"
DEMO_MODE = "무료 데모 (API 없이 규칙 기반)"

# app.py 를 모듈로 import 하지 않는다 - AppTest 가 별도 네임스페이스에서
# 실행하므로 다른 인스턴스가 된다. 라벨은 화면에서 읽는다.
SAMPLE_INPUT = {
    "코딩 도움": "클릭 횟수를 보여주는 버튼을 만들어 주세요.",
    "문서 요약 (영어)": (
        "The council approved a housing plan on Monday. Officials said it adds "
        "twelve thousand homes by 2030. Analysts warned delays could limit the effect."
    ),
    "문서 요약 (한국어)": (
        "정부는 15일 수도권 주택 공급을 늘리기 위한 대책을 발표했다. "
        "국토교통부에 따르면 2026년까지 신규 택지 12만 가구가 공급된다. "
        "전문가들은 단기 효과가 제한적이라고 전망했다."
    ),
    "고객 리뷰 작성": (
        "Visited the new ramen place near the station. Waited forty minutes. "
        "Broth was rich but the room was loud."
    ),
    "이메일 초안": (
        "Ask the vendor to confirm the Q4 delivery date and share the updated invoice."
    ),
}


def _category_labels() -> list[str]:
    app = AppTest.from_file(APP_PATH, default_timeout=30).run()
    assert not app.exception
    return list(app.selectbox[0].options)


def test_every_category_has_sample_input() -> None:
    """카테고리를 추가하고 이 테스트를 안 고치면 여기서 걸린다."""
    assert set(_category_labels()) == set(SAMPLE_INPUT)


def test_five_categories_are_exposed() -> None:
    """도메인 정의만 있고 앱에 안 붙은 카테고리가 생기는 것을 막는다."""
    labels = _category_labels()
    assert labels[0] == "코딩 도움", "첫 항목이 바뀌면 다른 테스트의 인덱스가 깨진다"
    assert len(labels) == 5


@pytest.mark.parametrize("label", sorted(SAMPLE_INPUT))
def test_category_completes_demo_run(label, monkeypatch) -> None:
    generator_module = importlib.import_module("engine.generator")

    def fail_if_called(*args, **kwargs):
        raise AssertionError("무료 데모에서 API 경로를 호출하면 안 됩니다.")

    monkeypatch.setattr(generator_module, "generate", fail_if_called)

    app = AppTest.from_file(APP_PATH, default_timeout=60).run()
    app.selectbox[0].select(label).run()
    app.radio(key="run_mode").set_value(DEMO_MODE).run()
    app.text_area[0].input(SAMPLE_INPUT[label]).run()
    app.button(key="start").click().run()
    assert not app.exception, f"{label}: 비교 시작에서 예외"
    assert app.session_state["stage"] == "compare"

    for round_index in range(8):
        # 두 후보가 같으면 그 선택에서 아무 정보도 얻지 못한다.
        shown = [m.value for m in app.markdown] + [w.value for w in app.text]
        assert shown, f"{label}: {round_index + 1}회차에 후보가 안 그려짐"
        app.button(key="pick_a").click().run()
        assert not app.exception, f"{label}: {round_index + 1}회차에서 예외"

    assert app.session_state["stage"] == "done", f"{label}: 완주 실패"
    # 완주 여부는 문구가 아니라 **산출물**로 본다. 화면 문구는 개편마다
    # 바뀌는데 프롬프트가 나왔는지는 바뀌지 않는 조건이다.
    assert app.code, "결과 화면에 시스템 프롬프트가 없습니다."
    assert app.code[0].value.strip()

    # 선호가 원시 JSON이 아니라 사람이 읽을 라벨로 나와야 한다.
    rendered = " ".join(m.value for m in app.markdown)
    assert "**" in rendered, f"{label}: 선호 라벨이 안 보인다"
    # 제목 순서에 기대지 않는다. 화면을 고칠 때마다 깨진다.
    assert app.code[0].value.strip(), "시스템 프롬프트가 비어 있습니다."
