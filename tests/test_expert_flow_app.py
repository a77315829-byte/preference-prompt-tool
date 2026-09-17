"""전문가 프롬프트 경로가 화면에서 끝까지 도는지, 그리고 API 를 전혀
쓰지 않는지 검증한다.

**API 를 안 쓴다는 것이 이 기능의 핵심 주장이다.** 사용자의 글을 모델에
보내지 않는다고 화면에 적어뒀으므로, 그 약속이 코드로 지켜지는지 테스트로
고정해야 한다. 나중에 누가 "여기서 한 번만 호출하면 더 좋을 텐데" 하고
넣으면 이 테스트가 막는다.
"""

import importlib
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"

EXPERT_PATH_LABEL = "내가 쓴 글에서 만들기 (자료 필요)"

# 저자 한 명의 글처럼 보이게 만든 자료. 답변마다 3문단, 문단마다 두 문장.
ANSWER = (
    "The short answer is that the fat matters more than the flour here. "
    "Suet melts slowly and leaves steam pockets behind.\n\n"
    "If you swap in butter you will get a denser crumb, because butter "
    "melts far earlier in the bake. That changes the texture completely.\n\n"
    "For a first attempt I would weigh everything and keep the mix cold. "
    "It is much easier to correct a dry dough than a greasy one."
)


def _paste(count: int) -> str:
    return "\n\n---\n\n".join([ANSWER] * count)


def _blocked_app(monkeypatch) -> AppTest:
    """API 경로를 전부 막아둔 앱. 호출하면 테스트가 실패한다."""
    generator = importlib.import_module("engine.generator")

    def fail_if_called(*args, **kwargs):
        raise AssertionError("이 경로는 모델을 호출하지 않아야 합니다.")

    for name in ("generate", "generate_all", "generate_with_prompt",
                 "generate_all_with_prompts"):
        monkeypatch.setattr(generator, name, fail_if_called)
    monkeypatch.setattr(
        importlib.import_module("optimize.run_gepa"), "run", fail_if_called
    )
    return AppTest.from_file(APP_PATH, default_timeout=30).run()


def test_expert_path_builds_a_prompt_without_calling_the_model(monkeypatch) -> None:
    app = _blocked_app(monkeypatch)
    app.radio(key="build_path").set_value(EXPERT_PATH_LABEL).run()
    assert not app.exception

    app.text_area[0].input(_paste(30)).run()
    assert not app.exception

    codes = [block.value for block in app.code]
    assert codes, "프롬프트가 화면에 나오지 않았습니다."
    assert any("words in total" in text for text in codes)
    assert any("sentences" in text for text in codes)


def test_expert_path_refuses_to_report_on_too_little_material(monkeypatch) -> None:
    """부족한 자료로 수치를 보여주면 사용자가 그걸 믿는다."""
    app = _blocked_app(monkeypatch)
    app.radio(key="build_path").set_value(EXPERT_PATH_LABEL).run()
    app.text_area[0].input(_paste(2)).run()
    assert not app.exception
    assert not app.code, "자료가 부족한데 프롬프트를 만들었습니다."
    assert any("필요합니다" in info.value for info in app.info)


def test_expert_path_warns_when_material_is_thin(monkeypatch) -> None:
    """최소는 넘겼지만 권장에 못 미치는 구간. 계산은 해주되 알려준다."""
    app = _blocked_app(monkeypatch)
    app.radio(key="build_path").set_value(EXPERT_PATH_LABEL).run()
    app.text_area[0].input(_paste(8)).run()
    assert not app.exception
    assert app.code, "최소 개수를 넘겼으면 프롬프트를 만들어야 합니다."
    assert any("30" in warning.value for warning in app.warning)


def test_expert_path_does_not_disturb_the_comparison_flow(monkeypatch) -> None:
    """규칙 10 - 신규 기능이 확보된 결과를 건드려서는 안 된다.

    경로를 갔다 돌아왔을 때 기존 비교 흐름이 그대로 시작되는지 본다.
    """
    app = _blocked_app(monkeypatch)
    app.radio(key="build_path").set_value(EXPERT_PATH_LABEL).run()
    app.radio(key="build_path").set_value("비교해서 만들기 (자료가 없어도 됩니다)").run()
    assert not app.exception
    assert app.selectbox[0].value == "코딩 도움"
    assert app.session_state["stage"] == "input"


def test_prompt_does_not_reference_examples_it_does_not_include(monkeypatch) -> None:
    """이 경로는 사용자의 글을 프롬프트에 넣지 않는다. 그러니 "아래 예시처럼"
    같은 문구를 쓰면 모델에게 없는 것을 따르라고 하는 셈이다.

    처음에 정확히 그렇게 써놨다가 실제 렌더를 보고 발견했다.
    """
    app = _blocked_app(monkeypatch)
    app.radio(key="build_path").set_value(EXPERT_PATH_LABEL).run()
    app.text_area[0].input(_paste(30)).run()

    prompt = app.code[0].value.lower()
    # "request below" 는 정당하다 - 사용자가 이 프롬프트 뒤에 실제 요청을
    # 붙인다. 문제는 **예시**를 가리키는 것이다. 처음 테스트가 "below"
    # 까지 금지해서 정상 문구를 잡아냈다.
    for phantom in ("example", "sample", "as written above"):
        assert phantom not in prompt, f"없는 것을 가리킨다: {phantom}"


def test_expert_feedback_is_logged_separately_and_without_text(monkeypatch) -> None:
    """이 기능의 만족도를 비교 경로와 합치면 아무 것도 말하지 못한다.
    그리고 붙여넣은 글이 로그로 새면 안 된다."""
    lines: list[str] = []
    feedback_module = importlib.import_module("feedback")
    original = feedback_module.FeedbackLog

    def capturing(*args, **kwargs):
        kwargs.pop("sink", None)
        return original(sink=lines.append, **kwargs)

    monkeypatch.setattr(feedback_module, "FeedbackLog", capturing)

    app = _blocked_app(monkeypatch)
    app.radio(key="build_path").set_value(EXPERT_PATH_LABEL).run()
    app.text_area[0].input(_paste(30)).run()

    # 응답 버튼을 누른다. "네, 맞아요" 가 첫 버튼이다.
    app.button(key="expert_fits_yes").click().run()
    assert not app.exception
    assert lines, "응답이 기록되지 않았습니다."

    import json

    record = json.loads(lines[0].split("USER_FEEDBACK ", 1)[1])
    assert record["mode"] == "expert", "비교 경로와 같은 모드로 집계됩니다."
    assert record["extra"]["answers"] == 30
    # 붙여넣은 글의 특징적인 단어가 어디에도 없어야 한다.
    assert "suet" not in json.dumps(record).lower()
