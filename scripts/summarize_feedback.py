"""배포 로그에서 실사용자 응답을 긁어 집계한다.

쓰는 법: Streamlit Cloud 콘솔에서 Manage app -> 로그를 텍스트 파일로
저장한 뒤,

    python -m scripts.summarize_feedback logs.txt

표준 입력도 받는다.

    type logs.txt | python -m scripts.summarize_feedback

왜 필요한가: 응답은 한 줄 JSON 으로 로그에 찍힌다(feedback.py). 저장소가
없어서 그렇게 했고, 사람이 읽을 형태로 되돌리는 것은 이 스크립트 몫이다.
한글은 로그에서 유니코드 escape 상태이므로 여기서 풀어 보여준다.

**모드는 합치지 않는다.** 세 가지가 서로 다른 것을 평가한다.

  api    : 실제 모델로 8회 비교해 만든 프롬프트. 개인화 검증의 주 근거.
  demo   : 규칙 기반 예시로 만든 것. 개인화 근거로는 약하다.
  expert : 자기 글을 붙여넣어 측정으로 만든 프롬프트. 기능이 다르다.

합쳐서 하나의 만족률을 내면 아무 것도 말하지 못한다.
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

    print("\n모드 설명: api = 실제 모델 비교, demo = 규칙 기반 비교, "
          "expert = 자기 글 측정")
    print("비교 기반 개인화의 근거는 api 행이고, expert 행은 별개 기능이다.")

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

    expert = [r for r in records if r.get("mode") == "expert"]
    if expert:
        counts = [r.get("extra", {}).get("answers") for r in expert]
        counts = [c for c in counts if isinstance(c, (int, float))]
        print(f"\nexpert 모드 상세 ({len(expert)}건)")
        if counts:
            print(f"  넣은 답변 개수: 최소 {min(counts):.0f} / 중앙 "
                  f"{sorted(counts)[len(counts) // 2]:.0f} / 최대 {max(counts):.0f}")
        # 자료가 적을 때 덜 만족하는지 본다. 실측에서 12개와 30개의 차이가
        # 컸으므로(한 저자는 -0.122 에서 +0.187 로 뒤집혔다) 실사용에서도
        # 그 경계가 보이는지 확인할 값이다.
        thin = [r for r in expert if (r.get("extra", {}).get("answers") or 0) < 30]
        thick = [r for r in expert if (r.get("extra", {}).get("answers") or 0) >= 30]
        for label, bucket in (("30개 미만", thin), ("30개 이상", thick)):
            if bucket:
                yes = sum(1 for r in bucket if r.get("fits"))
                print(f"  {label}: {len(bucket)}건 중 맞다 {yes}건 "
                      f"({yes / len(bucket):.0%})")

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
