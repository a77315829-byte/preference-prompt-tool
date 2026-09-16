"""실사용자 응답을 한 줄 로그로 남긴다.

Streamlit을 import하지 않는다. 그래서 UI 없이 그대로 단위 테스트할 수
있다 (tests/test_feedback.py).

왜 로그인가: 지금까지의 정량 결과는 전부 MACSum 페르소나 기반이고
"실제 사람도 이 결과를 좋아했다"는 근거가 하나도 없다. 예선 기간 공개
링크에 트래픽이 들어오므로 그 방문자가 그대로 표본이 된다. 다만 저장할
곳이 없다 - Streamlit Community Cloud 파일 시스템은 앱이 재시작되면
날아가고, 프로젝트 규칙상 서버형 DB는 쓰지 않는다. 표준 출력으로 찍으면
Streamlit Cloud 콘솔 로그에서 읽을 수 있고 새 의존성이 0개다. 투박하지만
2주 창에서는 충분히 돌아간다.

**원문과 생성 결과는 기록하지 않는다.** 개인 정보가 섞일 수 있고, 사용자가
공유할 의도로 넣은 값이 아니다. 남기는 것은 날짜, 도메인, 실행 모드,
예/아니오, 추정된 축 선호, 그리고 사용자가 직접 쓴 한 줄 의견뿐이다.

로그 한 줄에 누적 집계를 함께 실어 보낸다. 마지막 줄만 봐도 총계를 알 수
있어서 로그 전체를 파싱하지 않아도 된다. 앱이 재시작되면 누적값은 0으로
돌아가지만 이전에 찍힌 줄들은 로그에 남는다.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from typing import Callable

# 로그에서 이 줄만 골라내기 위한 고정 태그. 검색: grep USER_FEEDBACK
LOG_TAG = "USER_FEEDBACK"

# 의견 길이 상한. 로그 한 줄을 유지하고 콘솔이 잘리는 것을 막는다.
MAX_COMMENT_CHARS = 300


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _emit(line: str) -> None:
    """한 줄을 표준 출력으로 즉시 내보낸다.

    flush 가 필요하다. 표준 출력이 터미널이 아니라 파일·파이프로 갈 때
    파이썬은 블록 버퍼링을 하는데, 배포 환경이 바로 그 경우다. 로컬에서
    flush 없이 확인했을 때 UI 는 정상 동작했지만 로그에 아무 줄도 남지
    않았다 - 모으고 있다고 착각하기 딱 좋은 실패다.
    """
    print(line, flush=True)


class FeedbackLog:
    """예/아니오 응답을 세고 한 줄씩 기록한다."""

    def __init__(self, sink: Callable[[str], None] = _emit, clock=_utc_now) -> None:
        self._sink = sink
        self._clock = clock
        self._lock = threading.Lock()
        self._counts: dict[str, int] = {}

    def totals(self) -> dict[str, int]:
        """모드별 예/아니오 누적. 예: {"api:yes": 3, "api:no": 1}"""
        with self._lock:
            return dict(self._counts)

    def record(
        self,
        *,
        domain: str,
        demo_mode: bool,
        fits: bool,
        preferred: dict[str, str] | None = None,
        comment: str = "",
        rounds: int | None = None,
    ) -> dict:
        """응답 하나를 기록하고, 찍은 내용을 그대로 돌려준다."""
        mode = "demo" if demo_mode else "api"
        key = f"{mode}:{'yes' if fits else 'no'}"

        with self._lock:
            self._counts[key] = self._counts.get(key, 0) + 1
            totals = dict(self._counts)

        record = {
            "at": self._clock(),
            "domain": domain,
            "mode": mode,
            "fits": bool(fits),
            "preferred": dict(preferred or {}),
            "comment": _clean_comment(comment),
            "rounds": rounds,
            "totals": totals,
        }
        # ensure_ascii=True 로 한글을 유니코드 escape 로 바꿔 내보낸다.
        # 표준 출력의 인코딩은 환경에 따라 다르고(윈도우에서 파일로
        # 리다이렉트하면 cp949), 실제로 로컬 검증에서 로그 파일의 한글이
        # 깨졌다. 줄을 ASCII 로만 만들면 어느 환경에서도 그대로 남고
        # json.loads 가 원문을 정확히 복원한다. 사람이 읽을 때는
        # scripts/summarize_feedback.py 가 풀어서 보여준다.
        self._sink(f"{LOG_TAG} {json.dumps(record, ensure_ascii=True, sort_keys=True)}")
        return record


def _clean_comment(comment: str) -> str:
    """줄바꿈을 없애고 길이를 자른다. 로그 한 줄을 지켜야 파싱이 쉽다."""
    if not comment:
        return ""
    single_line = " ".join(comment.split())
    if len(single_line) <= MAX_COMMENT_CHARS:
        return single_line
    return single_line[: MAX_COMMENT_CHARS - 1] + "…"


def summarize(records: list[dict]) -> dict:
    """로그에서 긁어온 기록들을 집계한다. 발표용 수치를 낼 때 쓴다.

    demo 모드 응답은 규칙 기반 결과에 대한 평가라서 개인화 검증 근거로는
    약하다. 그래서 합치지 않고 모드별로 나눠 돌려준다.
    """
    summary: dict[str, dict[str, int]] = {}
    for record in records:
        mode = record.get("mode", "unknown")
        bucket = summary.setdefault(mode, {"yes": 0, "no": 0})
        bucket["yes" if record.get("fits") else "no"] += 1
    for bucket in summary.values():
        total = bucket["yes"] + bucket["no"]
        bucket["total"] = total
        bucket["yes_rate"] = round(bucket["yes"] / total, 3) if total else 0.0
    return summary
