"""CSS 문자열 생성. Streamlit 을 import 하지 않는다 (주입은 UI 쪽 일).

**Streamlit 버전에 묶인 선택자를 여기 한곳에 모아둔다.** `data-testid` 는
버전마다 바뀌고, 바뀌면 화면이 조용히 깨진다(에러가 아니라 스타일만 빠진다).
`requirements.txt` 가 streamlit 을 정확히 고정하는 이유가 이것이고, 올릴
때는 아래 목록만 확인하면 된다.

    검증한 버전: streamlit 1.63.0

    [data-testid="stHeader"]          상단 헤더 바
    [data-testid="stToolbar"]         우상단 햄버거·Deploy 영역
    [data-testid="stDecoration"]      헤더 위 그라디언트 띠
    [data-testid="stMainBlockContainer"]  본문 컨테이너 (상단 패딩 제거용)
    [data-testid="stSidebar"]         사이드바 (쓰지 않지만 흔적 제거)
    [data-testid="stTextArea"] textarea   원문 입력 - 모노 폰트 적용
    [data-testid="stCodeBlock"]       st.code 출력 - 프롬프트 표시
    [data-testid="stBaseButton-secondary"] 기본 버튼
    footer                            "Made with Streamlit"

선택자가 하나 빠져도 기능은 살아 있어야 한다. 그래서 전부 **장식만**
건드린다 - 레이아웃을 선택자에 의존하지 않는다.
"""

from __future__ import annotations

# --- 디자인 토큰 -------------------------------------------------------------
# accent 는 선택·확정·CTA·게이지에만 쓴다. 나머지는 전부 무채색이다.
TOKENS = {
    "bg": "#0B0C0E",
    "surface": "#141619",
    "surface-raised": "#1C1F24",
    "border": "#262A30",
    "text-primary": "#E8EAED",
    "text-secondary": "#9BA1A9",
    "text-muted": "#5F666E",
    "accent": "#D7FF3E",
    "accent-dim": "rgba(215,255,62,.12)",
    "axis-1": "#D7FF3E",
    "axis-2": "#5EC8FF",
    "axis-3": "#FF8A5B",
}

# 축 색. 축 개수가 도메인마다 다르므로(요약 2개, 코딩 3개) 순환시킨다.
AXIS_COLORS = ("axis-1", "axis-2", "axis-3")

# 카드 최소 높이(px). **후보 길이가 달라도 레이아웃이 흔들리면 안 된다** -
# 흔들리면 사용자가 내용이 아니라 흔들림을 보고 고르게 되고, 그게 곧
# length 축 판단 오염이다.
CARD_MIN_HEIGHT = 320

# 게이지 애니메이션. rerun 마다 DOM 이 새로 그려져 transition 이 안 먹으므로
# keyframes 를 매번 새 이름으로 만들어 걸어야 한다.
GAUGE_DURATION_MS = 400
GAUGE_EASING = "cubic-bezier(.2,.8,.2,1)"

# 웹폰트. CSS @import 로 CDN 에서 가져온다.
FONT_IMPORTS = (
    "@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/"
    "dist/web/variable/pretendardvariable-dynamic-subset.min.css');"
    "@import url('https://fonts.googleapis.com/css2?"
    "family=JetBrains+Mono:wght@400;500;700&display=swap');"
)

FONT_SANS = (
    "'Pretendard Variable', Pretendard, -apple-system, BlinkMacSystemFont, "
    "system-ui, sans-serif"
)
FONT_MONO = "'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace"


def _variables() -> str:
    body = "".join(f"--{name}:{value};" for name, value in TOKENS.items())
    return (
        ":root{"
        + body
        + f"--font-sans:{FONT_SANS};--font-mono:{FONT_MONO};"
        + f"--card-min-h:{CARD_MIN_HEIGHT}px;"
        + "}"
    )


def base_css() -> str:
    """토큰 · 기본 타이포 · Streamlit 기본 UI 제거 · 컴포넌트 스타일.

    한 번만 주입한다. 그림자는 쓰지 않고 1px 경계선으로 해결한다.
    """
    return f"<style>{FONT_IMPORTS}{_variables()}{_reset()}{_components()}</style>"


def _reset() -> str:
    return """
    /* Streamlit 기본 UI 제거. 장식만 건드린다 - 선택자가 바뀌어도
       기능이 죽지 않게. */
    [data-testid="stHeader"],
    [data-testid="stToolbar"],
    [data-testid="stDecoration"],
    [data-testid="stSidebar"],
    footer { display: none !important; }
    [data-testid="stMainBlockContainer"] { padding-top: 2.5rem; max-width: 1200px; }

    .stApp, body { background: var(--bg); color: var(--text-primary);
                   font-family: var(--font-sans); }
    body { line-height: 1.65; }
    h1, h2, h3, h4 { font-family: var(--font-sans); line-height: 1.25;
                     letter-spacing: -0.01em; }

    /* 숫자·라벨·프롬프트는 반드시 모노. tabular-nums 로 자리가 흔들리지
       않게 한다 - 게이지 옆 숫자가 매 라운드 흔들리면 계측기로 안 보인다. */
    [data-testid="stTextArea"] textarea,
    [data-testid="stCodeBlock"], [data-testid="stCodeBlock"] code {
        font-family: var(--font-mono) !important;
        font-variant-numeric: tabular-nums;
        font-size: 13px !important;
    }
    [data-testid="stTextArea"] textarea {
        background: var(--surface) !important;
        border: 1px solid var(--border) !important;
        color: var(--text-primary) !important;
        border-radius: 6px !important;
    }
    [data-testid="stTextArea"] textarea:focus {
        border-color: var(--accent) !important;
        box-shadow: none !important;
    }
    [data-testid="stCodeBlock"] {
        background: var(--surface) !important;
        border: 1px solid var(--border); border-radius: 10px;
    }
    """


def _components() -> str:
    return f"""
    .ppt-label {{ font-family: var(--font-mono); font-size: 12px;
                  text-transform: uppercase; letter-spacing: .08em;
                  color: var(--text-muted); }}
    .ppt-eyebrow {{ font-family: var(--font-mono); font-size: 12px;
                    text-transform: uppercase; letter-spacing: .08em;
                    color: var(--accent); }}
    .ppt-mono {{ font-family: var(--font-mono);
                 font-variant-numeric: tabular-nums; }}

    /* 라운드 스테퍼. 도트 8개, 완료/현재/대기 3상태. */
    .ppt-stepper {{ display: flex; gap: 6px; margin: 8px 0 24px; }}
    .ppt-dot {{ width: 8px; height: 8px; border-radius: 2px;
                background: var(--border); }}
    .ppt-dot.done {{ background: var(--text-muted); }}
    .ppt-dot.now {{ background: var(--accent); }}

    /* 게이지. 값은 확신도가 아니라 "그 축이 갈린 비교 횟수"다 - 확신도는
       3값 축에서 24회까지 0.06 에 머물러 차오르지 않는다(실측). */
    .ppt-gauge {{ margin-bottom: 20px; }}
    /* gap 을 준다. 축 이름이 길면(style_management) 숫자와 붙어버린다. */
    .ppt-gauge-head {{ display: flex; justify-content: space-between;
                       align-items: baseline; gap: 8px; margin-bottom: 6px; }}
    .ppt-gauge-name {{ font-family: var(--font-mono); font-size: 11px;
                       text-transform: uppercase; letter-spacing: .06em;
                       color: var(--text-secondary); overflow: hidden;
                       text-overflow: ellipsis; white-space: nowrap; }}
    .ppt-gauge-count {{ font-family: var(--font-mono); font-size: 11px;
                        flex: 0 0 auto;
                        font-variant-numeric: tabular-nums;
                        color: var(--text-muted); }}
    .ppt-gauge-track {{ height: 4px; border-radius: 2px;
                        background: var(--surface-raised); overflow: hidden; }}
    .ppt-gauge-fill {{ height: 100%; border-radius: 2px; }}
    .ppt-gauge-est {{ font-family: var(--font-mono); font-size: 13px;
                      color: var(--text-primary); margin-top: 6px; }}
    .ppt-gauge-est .none {{ color: var(--text-muted); }}

    /* A/B 카드. min-height 고정이 핵심이다. */
    .ppt-card {{ background: var(--surface); border: 1px solid var(--border);
                 border-radius: 10px; padding: 20px;
                 min-height: var(--card-min-h);
                 display: flex; flex-direction: column; gap: 12px; }}
    .ppt-card-badge {{ font-family: var(--font-mono); font-size: 12px;
                       letter-spacing: .08em; color: var(--text-muted); }}
    .ppt-card-body {{ font-size: 14px; color: var(--text-primary);
                      white-space: pre-wrap; }}

    /* 버튼을 카드와 이어진 것처럼. 위쪽 모서리를 없애고 경계선을 잇는다. */
    [data-testid="stBaseButton-secondary"] {{
        background: var(--surface-raised); color: var(--text-primary);
        border: 1px solid var(--border); border-radius: 6px;
        font-family: var(--font-mono); font-size: 13px;
        letter-spacing: .04em; transition: border-color 150ms ease-out,
        background 150ms ease-out, transform 150ms ease-out;
    }}
    [data-testid="stBaseButton-secondary"]:hover {{
        border-color: var(--accent); background: var(--accent-dim);
    }}
    [data-testid="stBaseButton-secondary"]:active {{ transform: scale(.99); }}

    /* 진행 바. 게이지와 같은 시각 언어. 스피너를 쓰지 않는다. */
    .ppt-progress {{ height: 4px; border-radius: 2px;
                     background: var(--surface-raised); overflow: hidden; }}
    .ppt-progress-fill {{ height: 100%; background: var(--accent);
                          border-radius: 2px; }}

    .ppt-badge {{ display: inline-block; font-family: var(--font-mono);
                  font-size: 12px; padding: 4px 8px; border-radius: 6px;
                  border: 1px solid var(--border); color: var(--text-secondary);
                  margin: 0 6px 6px 0; }}
    .ppt-keyhint {{ font-family: var(--font-mono); font-size: 12px;
                    color: var(--text-muted); letter-spacing: .04em; }}

    @media (prefers-reduced-motion: reduce) {{
        .ppt-gauge-fill, [data-testid="stBaseButton-secondary"] {{
            animation: none !important; transition: none !important;
        }}
    }}
    """


def gauge_keyframes(previous: list[float], current: list[float], round_no: int) -> str:
    """게이지마다 `이전 -> 현재` 키프레임을 만든다.

    **왜 transition 이 아니라 keyframes 인가.** Streamlit 은 rerun 마다 DOM
    을 새로 그린다. 새로 만들어진 요소에 transition 을 걸어도 시작값이
    없어서 애니메이션이 일어나지 않는다. 그래서 from/to 를 명시한
    keyframes 를 매 렌더에 생성해 붙인다.

    이름에 라운드 번호가 들어가야 한다. 같은 이름이면 브라우저가 이미
    재생한 애니메이션으로 보고 다시 재생하지 않는다.
    """
    blocks = []
    for index, (before, after) in enumerate(zip(previous, current)):
        blocks.append(
            f"@keyframes ppt-fill-{index}-{round_no}"
            f"{{from{{width:{before * 100:.2f}%}}to{{width:{after * 100:.2f}%}}}}"
        )
    return "<style>" + "".join(blocks) + "</style>"


def gauge_html(
    name: str,
    estimate: str | None,
    fill: float,
    discriminated: int,
    total: int,
    index: int,
    round_no: int,
) -> str:
    """게이지 하나. 애니메이션 이름은 `gauge_keyframes` 와 맞춰야 한다."""
    color = f"var(--{AXIS_COLORS[index % len(AXIS_COLORS)]})"
    shown = (
        f"{estimate}" if estimate else '<span class="none">아직 추정 전</span>'
    )
    return (
        '<div class="ppt-gauge">'
        '<div class="ppt-gauge-head">'
        f'<span class="ppt-gauge-name">{name}</span>'
        f'<span class="ppt-gauge-count">{discriminated}/{total}</span>'
        "</div>"
        '<div class="ppt-gauge-track">'
        f'<div class="ppt-gauge-fill" style="width:{fill * 100:.2f}%;'
        f"background:{color};"
        f"animation:ppt-fill-{index}-{round_no} {GAUGE_DURATION_MS}ms {GAUGE_EASING} both\"></div>"
        "</div>"
        f'<div class="ppt-gauge-est">{shown}</div>'
        "</div>"
    )


def stepper_html(answered: int, total: int) -> str:
    """완료/현재/대기 3상태 도트."""
    dots = []
    for index in range(total):
        if index < answered:
            state = "done"
        elif index == answered:
            state = "now"
        else:
            state = ""
        dots.append(f'<div class="ppt-dot {state}"></div>')
    return '<div class="ppt-stepper">' + "".join(dots) + "</div>"


def card_badge_html(badge: str) -> str:
    """카드 상단의 A/B 표식.

    **본문은 여기서 그리지 않는다.** 처음엔 본문까지 HTML 로 넣었는데 두
    가지가 깨졌다. (1) 코딩 도메인 후보는 마크다운 코드 펜스를 담고 있어서,
    이스케이프한 뒤 `st.markdown` 이 다시 처리해 `&quot;` 가 글자로 보였다.
    (2) `min-height` 만으로는 내용이 넘칠 때 카드가 늘어나 두 카드 높이가
    달라졌다.

    그래서 본문은 `st.container(border=True, height=CARD_MIN_HEIGHT)` 안에
    Streamlit 이 직접 그리게 한다 - 높이가 진짜로 고정되고 넘치면 안에서
    스크롤된다. 후보 길이가 레이아웃을 흔들지 않는 것이 length 축 판단
    오염을 막는 장치다.
    """
    return f'<div class="ppt-card-badge">{_escape(badge)}</div>'


def progress_html(value: float, label: str) -> str:
    """가느다란 진행 바. 스피너를 쓰지 않는 이유는 계측기 톤을 지키려는
    것이고, 게이지와 같은 시각 언어를 쓴다."""
    return (
        f'<div class="ppt-label" style="margin-bottom:8px">{_escape(label)}</div>'
        '<div class="ppt-progress">'
        f'<div class="ppt-progress-fill" style="width:{max(0.0, min(1.0, value)) * 100:.1f}%"></div>'
        "</div>"
    )


def badges_html(items: list[tuple[str, str]]) -> str:
    return "".join(
        f'<span class="ppt-badge">{_escape(name)} = {_escape(value)}</span>'
        for name, value in items
    )


def _escape(text: str) -> str:
    """HTML 로 넣는 값은 반드시 이스케이프한다.

    카드 본문은 모델이 만든 텍스트고 원문은 사용자가 붙여넣은 것이다.
    그대로 넣으면 `<script>` 가 실행된다 - `unsafe_allow_html=True` 로
    주입하므로 여기서 막는 것이 유일한 방어선이다.
    """
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
