"""배포된 앱을 실제 브라우저로 열어 살아있는지 확인한다.

두 가지 일을 한다.

1. **절전 방지.** Streamlit Community Cloud는 트래픽이 12시간 없으면 앱을
   재운다. 깨어난 앱을 처음 보는 사람은 30초를 기다린다. 단순 HTTP GET은
   SPA 껍데기만 받아가고 Streamlit 세션(웹소켓)을 열지 않아서 트래픽으로
   집계되는지 확신할 수 없다. 그래서 실제 브라우저로 세션을 맺는다.
2. **스모크 테스트.** 화면에 실제 위젯과 히어로 문구가 그려지는지 본다.
   앱이 죽거나 깨지면 0이 아닌 코드로 끝나므로, CI에서 돌리면 메일이 온다.

로컬 실행:
    python -m scripts.smoke_live
    python -m scripts.smoke_live --url https://.../

playwright는 이 스크립트와 CI에서만 쓴다. requirements.txt(배포)와
requirements-dev.txt(실험)에는 넣지 않는다 - 배포 이미지를 무겁게 만들
이유가 없다.
"""

from __future__ import annotations

import argparse
import sys
import time

DEFAULT_URL = "https://preference-prompt-tool-7c9fvm3tb5bfxv8v6648fu.streamlit.app/"

# 화면에 반드시 보여야 하는 문구. app.py의 히어로 뱃지에서 온다.
# 눈에 보이는 문구를 쓰는 이유: 예전에 입력란의 maxlength 속성을 배포 확인
# 마커로 썼다가 낭패를 봤다. Streamlit이 max_chars를 DOM 속성으로 찍지
# 않아서, 존재한 적 없는 표식을 기다린 셈이었다.
EXPECTED_TEXT = "번의 선택으로 완성"

WAKE_BUTTON = "text=Yes, get this app back up!"

# 절전에서 깨는 데 30초 안팎 걸린다. 여유를 둔다.
WAKE_WAIT_SECONDS = 60
WIDGET_TIMEOUT_MS = 180_000


def _app_frame(page):
    """앱 위젯이 있는 프레임을 찾는다.

    배포된 Streamlit 화면은 같은 출처의 중첩 iframe 안에 들어있는 경우가
    있어서, 메인 프레임만 보면 빈 본문을 읽는다.
    """
    for frame in page.frames:
        try:
            if frame.locator("[data-testid='stSelectbox']").count() > 0:
                return frame
        except Exception:  # noqa: BLE001 - 전환 중인 프레임은 건너뛴다
            continue
    return None


def check(url: str, *, headless: bool = True) -> int:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless)
        page = browser.new_page()
        try:
            page.goto(url, wait_until="load", timeout=120_000)

            # 잠들어 있으면 깨운다. 이 클릭이 곧 트래픽이다.
            try:
                if "get this app back up" in page.content():
                    print("앱이 절전 상태였다. 깨운다.")
                    try:
                        page.click(WAKE_BUTTON, timeout=10_000)
                    except Exception:  # noqa: BLE001 - 이미 깨어나는 중일 수 있다
                        pass
                    time.sleep(WAKE_WAIT_SECONDS)
            except Exception:  # noqa: BLE001
                pass

            deadline = time.time() + WIDGET_TIMEOUT_MS / 1000
            frame = None
            while time.time() < deadline:
                frame = _app_frame(page)
                if frame is not None:
                    break
                time.sleep(5)

            if frame is None:
                print("FAIL: 제한 시간 안에 앱 위젯이 그려지지 않았다.")
                return 1

            body = frame.inner_text("body")
            for marker in ("Traceback", "ModuleNotFoundError", "Error running app"):
                if marker in body:
                    print(f"FAIL: 앱이 오류 화면을 띄웠다 ({marker}).")
                    print(body[:800])
                    return 1

            if EXPECTED_TEXT not in body:
                print(f"FAIL: 기대한 문구를 못 찾았다: {EXPECTED_TEXT!r}")
                print(body[:800])
                return 1

            print(f"OK: 앱이 응답하고 화면이 정상이다 ({url})")
            return 0
        finally:
            browser.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL, help="확인할 배포 주소")
    parser.add_argument("--headed", action="store_true", help="브라우저를 띄워서 확인")
    args = parser.parse_args()
    return check(args.url, headless=not args.headed)


if __name__ == "__main__":
    sys.exit(main())
