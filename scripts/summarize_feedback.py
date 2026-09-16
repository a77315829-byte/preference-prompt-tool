"""배포 로그에서 실사용자 응답을 긁어 집계한다.

쓰는 법: Streamlit Cloud 콘솔에서 Manage app -> 로그를 텍스트 파일로
저장한 뒤,

    python -m scripts.summarize_feedback logs.txt

표준 입력도 받는다.

    type logs.txt | python -m scripts.summarize_feedback

왜 필요한가: 응답은 한 줄 JSON 으로 로그에 찍힌다(feedback.py). 저장소가
없어서 그렇게 했고, 사람이 읽을 형태로 되돌리는 것은 이 스크립트 몫이다.
한글은 로그에서 유니코드 escape 상태이므로 여기서 풀어 보여준다.

**demo 모드 응답은 합치지 않는다.** 규칙 기반 결과에 대한 평가라서 개인화
검증 근거로는 약하다. 모드별로 나눠서 보고해야 정직하다.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from feedback import LOG_TAG, summarize  # noqa: E402


def parse_lines(lines) -> list[dict]:
    records = []
    for line in lines:
        if LOG_TAG not in line:
            continue
        payload = line.split(LOG_TAG, 1)[1].strip()
        try:
            records.append(json.loads(payload))
        except json.JSONDecodeError:
            # 로그가 중간에 잘렸을 수 있다. 조용히 버리지 않고 알린다.
            print(f"건너뜀 (JSON 파싱 실패): {payload[:80]}", file=sys.stderr)
    return records


def report(records: list[dict]) -> None:
    if not records:
        print("응답이 없다. 로그에 USER_FEEDBACK 줄이 있는지 확인할 것.")
        return

    summary = summarize(records)
    print(f"수집된 응답: {len(records)}건\n")

    print(f"{'모드':6} {'응답':>5} {'맞다':>5} {'아쉽다':>6} {'만족률':>7}")
    for mode in sorted(summary):
        bucket = summary[mode]
        print(
            f"{mode:6} {bucket['total']:5d} {bucket['yes']:5d} "
            f"{bucket['no']:6d} {bucket['yes_rate']:7.0%}"
        )

    print("\n모드 설명: api = 실제 모델 생성, demo = 규칙 기반 예시")
    print("개인화 검증 근거로는 api 행만 쓸 것.")

    by_domain: dict[str, dict[str, int]] = {}
    for record in records:
        if record.get("mode") != "api":
            continue
        bucket = by_domain.setdefault(record.get("domain", "unknown"), {"yes": 0, "no": 0})
        bucket["yes" if record.get("fits") else "no"] += 1
    if by_domain:
        print(f"\napi 모드 카테고리별\n{'카테고리':20} {'맞다':>5} {'아쉽다':>6}")
        for domain in sorted(by_domain):
            bucket = by_domain[domain]
            print(f"{domain:20} {bucket['yes']:5d} {bucket['no']:6d}")

    comments = [
        (record.get("domain", "?"), record.get("fits"), record["comment"])
        for record in records
        if record.get("comment")
    ]
    if comments:
        print(f"\n남긴 의견 {len(comments)}건")
        for domain, fits, comment in comments:
            mark = "O" if fits else "X"
            print(f"  [{mark}] ({domain}) {comment}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", nargs="?", help="로그 파일 경로 (없으면 표준 입력)")
    args = parser.parse_args()

    # 로그 파일 인코딩은 환경마다 다를 수 있다. 줄 자체는 ASCII 라서
    # errors="replace" 로 읽어도 USER_FEEDBACK 줄은 온전하다.
    if args.log:
        lines = Path(args.log).read_text(encoding="utf-8", errors="replace").splitlines()
    else:
        lines = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8", errors="replace").read().splitlines()

    report(parse_lines(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
