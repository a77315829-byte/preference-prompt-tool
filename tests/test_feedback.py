"""실사용자 응답 기록(feedback.py) 검증.

Streamlit 없이 돈다. 기록 형식이 깨지면 심사 기간에 모은 데이터를
읽을 수 없게 되므로, 형식과 개인정보 제외를 둘 다 고정한다.
"""

import json
import threading

import pytest

from feedback import LOG_TAG, MAX_COMMENT_CHARS, FeedbackLog, summarize


@pytest.fixture
def log():
    lines: list[str] = []
    return FeedbackLog(sink=lines.append, clock=lambda: "2026-09-16T12:00:00+00:00"), lines


def _parse(line: str) -> dict:
    assert line.startswith(LOG_TAG + " "), line
    return json.loads(line[len(LOG_TAG) + 1 :])


def test_record_is_one_parseable_line(log) -> None:
    feedback, lines = log
    feedback.record(domain="summarization_ko", demo_mode=False, fits=True, rounds=8)
    assert len(lines) == 1
    assert "\n" not in lines[0]
    parsed = _parse(lines[0])
    assert parsed["domain"] == "summarization_ko"
    assert parsed["mode"] == "api"
    assert parsed["fits"] is True
    assert parsed["rounds"] == 8


def test_demo_mode_is_labelled_separately(log) -> None:
    """데모 모드 응답은 규칙 기반 결과에 대한 평가라서 섞으면 안 된다."""
    feedback, lines = log
    feedback.record(domain="review", demo_mode=True, fits=True)
    assert _parse(lines[0])["mode"] == "demo"


def test_source_text_is_never_logged(log) -> None:
    """원문·생성 결과는 기록하지 않는다. 개인 정보가 섞일 수 있고 사용자가
    공유할 의도로 넣은 값이 아니다."""
    feedback, lines = log
    feedback.record(
        domain="email",
        demo_mode=False,
        fits=False,
        preferred={"length": "short"},
        comment="짧아서 좋았어요",
    )
    parsed = _parse(lines[0])
    assert set(parsed) == {
        "at", "domain", "mode", "fits", "preferred", "comment", "rounds", "totals"
    }
    assert parsed["preferred"] == {"length": "short"}
    assert parsed["comment"] == "짧아서 좋았어요"


def test_comment_is_flattened_and_capped(log) -> None:
    feedback, lines = log
    feedback.record(
        domain="review", demo_mode=False, fits=True,
        comment="첫 줄\n두 번째 줄\t탭\n\n" + "가" * 500,
    )
    comment = _parse(lines[0])["comment"]
    assert "\n" not in comment
    assert "\t" not in comment
    assert len(comment) <= MAX_COMMENT_CHARS
    assert comment.startswith("첫 줄 두 번째 줄 탭 ")


def test_missing_comment_is_empty_string(log) -> None:
    feedback, lines = log
    feedback.record(domain="coding", demo_mode=False, fits=True)
    assert _parse(lines[0])["comment"] == ""


def test_running_totals_ride_along(log) -> None:
    """마지막 줄만 봐도 총계를 알 수 있어야 로그를 다 파싱하지 않아도 된다."""
    feedback, lines = log
    feedback.record(domain="review", demo_mode=False, fits=True)
    feedback.record(domain="review", demo_mode=False, fits=True)
    feedback.record(domain="review", demo_mode=False, fits=False)
    feedback.record(domain="review", demo_mode=True, fits=True)

    assert _parse(lines[-1])["totals"] == {"api:yes": 2, "api:no": 1, "demo:yes": 1}
    assert feedback.totals() == {"api:yes": 2, "api:no": 1, "demo:yes": 1}


def test_concurrent_records_are_all_counted() -> None:
    """방문자 여러 명이 동시에 답할 수 있다. 카운터가 유실되면 표본이 줄어든다."""
    lines: list[str] = []
    guard = threading.Lock()

    def sink(line: str) -> None:
        with guard:
            lines.append(line)

    feedback = FeedbackLog(sink=sink)
    start = threading.Event()

    def worker(index: int) -> None:
        start.wait()
        feedback.record(domain="review", demo_mode=False, fits=index % 2 == 0)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(60)]
    for t in threads:
        t.start()
    start.set()
    for t in threads:
        t.join()

    assert len(lines) == 60
    assert sum(feedback.totals().values()) == 60


def test_summarize_splits_modes_and_computes_rate() -> None:
    records = [
        {"mode": "api", "fits": True},
        {"mode": "api", "fits": True},
        {"mode": "api", "fits": False},
        {"mode": "demo", "fits": False},
    ]
    summary = summarize(records)
    assert summary["api"] == {"yes": 2, "no": 1, "total": 3, "yes_rate": 0.667}
    assert summary["demo"] == {"yes": 0, "no": 1, "total": 1, "yes_rate": 0.0}


def test_summarize_handles_empty_input() -> None:
    assert summarize([]) == {}


def test_default_sink_flushes(capfd) -> None:
    """기본 sink 가 flush 하지 않으면 배포 로그에 아무것도 남지 않는다.

    표준 출력이 파일·파이프일 때 파이썬은 블록 버퍼링을 한다. 실제로
    로컬 확인에서 UI 는 정상이었는데 로그가 비어 있었다.
    """
    FeedbackLog(clock=lambda: "2026-09-16T12:00:00+00:00").record(
        domain="review", demo_mode=False, fits=True
    )
    out, _ = capfd.readouterr()
    assert LOG_TAG in out
    assert json.loads(out.strip()[len(LOG_TAG) + 1 :])["domain"] == "review"


def test_line_is_ascii_only_but_round_trips_korean(log) -> None:
    """표준 출력 인코딩은 환경마다 다르다. 윈도우에서 파일로 리다이렉트하면
    cp949 로 써서 실제로 로그의 한글이 깨졌다. 줄을 ASCII 로만 만들어
    그 의존을 없앤다."""
    feedback, lines = log
    feedback.record(
        domain="summarization_ko", demo_mode=False, fits=False,
        preferred={"length": "short"}, comment="표현이 너무 딱딱해요",
    )
    line = lines[0]
    line.encode("ascii")  # 비ASCII가 있으면 여기서 터진다
    assert _parse(line)["comment"] == "표현이 너무 딱딱해요"
