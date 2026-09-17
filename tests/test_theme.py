"""CSS 생성기를 검사한다.

Streamlit 없이 돈다. 여기서 막아야 하는 것이 둘이다.

1. **HTML 이스케이프.** `unsafe_allow_html=True` 로 주입하므로 카드 본문
   (모델 출력)과 원문(사용자 입력)을 그대로 넣으면 스크립트가 실행된다.
   이스케이프가 유일한 방어선이다.
2. **게이지 애니메이션 이름.** 라운드마다 이름이 달라야 재생된다. 같으면
   브라우저가 이미 재생한 것으로 보고 넘어가서, 바가 움직이지 않는다 -
   에러가 아니라 조용히 안 움직인다.
"""

from __future__ import annotations

import re

import theme


def test_base_css_declares_every_token() -> None:
    css = theme.base_css()
    for name in theme.TOKENS:
        assert f"--{name}:" in css, name


def test_base_css_hides_streamlit_chrome() -> None:
    """상단 헤더·푸터가 남으면 계측기 톤이 깨진다."""
    css = theme.base_css()
    for selector in ('[data-testid="stHeader"]', '[data-testid="stToolbar"]', "footer"):
        assert selector in css, selector


def test_base_css_has_no_box_shadow() -> None:
    """토큰 규칙 - 그림자 금지, 1px 경계선으로 해결."""
    body = theme.base_css()
    # box-shadow: none 으로 Streamlit 기본값을 지우는 것은 허용한다.
    declared = re.findall(r"box-shadow:\s*([^;!]+)", body)
    assert all(value.strip() == "none" for value in declared), declared


def test_card_badge_is_escaped() -> None:
    html = theme.card_badge_html('<script>alert("x")</script>')
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_gauge_keyframe_name_changes_every_round() -> None:
    first = theme.gauge_keyframes([0.0], [0.25], round_no=1)
    second = theme.gauge_keyframes([0.25], [0.5], round_no=2)
    assert "ppt-fill-0-1" in first
    assert "ppt-fill-0-2" in second
    assert "ppt-fill-0-1" not in second


def test_gauge_keyframes_animate_from_the_previous_value() -> None:
    """from 이 현재값이면 움직이지 않는다. 이전값이 들어가야 한다."""
    css = theme.gauge_keyframes([0.25], [0.50], round_no=3)
    assert "from{width:25.00%}" in css
    assert "to{width:50.00%}" in css


def test_gauge_html_matches_the_keyframe_name() -> None:
    """이름이 어긋나면 애니메이션이 안 걸린다. 둘을 같이 고정한다."""
    html = theme.gauge_html("length", "short", 0.5, 4, 8, index=0, round_no=3)
    assert "animation:ppt-fill-0-3" in html
    assert "4/8" in html
    assert "short" in html


def test_gauge_html_says_so_before_any_estimate() -> None:
    html = theme.gauge_html("length", None, 0.0, 0, 8, index=0, round_no=1)
    assert "아직 추정 전" in html


def test_gauge_colors_cycle_for_domains_with_more_axes() -> None:
    """축 개수는 도메인마다 다르다 (요약 2개, 코딩 3개). 색이 부족해도
    IndexError 로 죽으면 안 된다."""
    for index in range(5):
        html = theme.gauge_html("axis", "v", 0.1, 1, 8, index=index, round_no=1)
        assert "var(--axis-" in html


def test_stepper_marks_done_current_and_waiting() -> None:
    html = theme.stepper_html(answered=3, total=8)
    assert html.count("ppt-dot done") == 3
    assert html.count("ppt-dot now") == 1
    assert html.count("ppt-dot") == 8


def test_stepper_has_no_current_dot_when_finished() -> None:
    html = theme.stepper_html(answered=8, total=8)
    assert html.count("ppt-dot done") == 8
    assert "now" not in html


def test_progress_clamps_out_of_range_values() -> None:
    assert "width:100.0%" in theme.progress_html(1.4, "최적화")
    assert "width:0.0%" in theme.progress_html(-0.2, "최적화")


def test_progress_label_is_escaped() -> None:
    assert "&lt;b&gt;" in theme.progress_html(0.5, "<b>x</b>")


def test_badges_escape_both_name_and_value() -> None:
    html = theme.badges_html([("<axis>", "<value>")])
    assert "<axis>" not in html and "&lt;axis&gt;" in html
    assert "<value>" not in html and "&lt;value&gt;" in html


def test_card_height_is_a_fixed_number() -> None:
    """후보 길이에 따라 카드 높이가 흔들리면 사용자가 내용이 아니라
    흔들림을 보고 고른다. 그게 length 축 판단 오염이다.

    높이는 st.container(height=...) 로 넘기므로 숫자여야 한다.
    """
    assert isinstance(theme.CARD_MIN_HEIGHT, int)
    assert theme.CARD_MIN_HEIGHT >= 200


def test_config_toml_matches_the_tokens() -> None:
    """Streamlit 이 그리는 위젯과 우리가 그리는 HTML 의 색이 어긋나면
    안 된다. 토큰을 고치고 config 를 잊는 것을 막는다."""
    import pathlib
    import tomllib

    config = tomllib.loads(
        pathlib.Path(".streamlit/config.toml").read_text(encoding="utf-8")
    )["theme"]
    assert config["primaryColor"] == theme.TOKENS["accent"]
    assert config["backgroundColor"] == theme.TOKENS["bg"]
    assert config["secondaryBackgroundColor"] == theme.TOKENS["surface"]
    assert config["textColor"] == theme.TOKENS["text-primary"]
