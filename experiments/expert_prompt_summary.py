"""사이트별 결과 파일을 합쳐 제품에 넣을 최종 수치를 낸다.

`expert_prompt_eval_se.py` 는 사이트 하나씩 돌리고 파일도 따로 쓴다.
그러면 저자 8명을 한 표로 볼 수 없고, **절대 규칙 11** 이 요구하는
"평균으로 읽어라"를 지키기가 어렵다. 이 스크립트가 그 합치는 일을 한다.

**왜 평균을 강조하나.** 저자별 홀드아웃 15개에서 "앵커가 해로웠다"던
3명 중 2명이 홀드아웃 45개에서 부호가 뒤집혔다. 케이스 단위 수치의 작은
차이는 잡음이다. 그래서 여기서는 평균과 함께 **저자별 승패 수와 부호검정**
을 낸다 - 방향이 일관적인지를 보려면 그게 맞는 형태다.

실행:
    python -m experiments.expert_prompt_summary
    python -m experiments.expert_prompt_summary --pattern "final_train30_*.json"
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

from experiments.expert_prompt_eval import sign_test_p

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "experiments" / "results"

# 기준 조건. 이득은 항상 이것과의 차이로 말한다.
BASELINE = "base"


def load(pattern: str) -> list[dict]:
    rows = []
    for path in sorted(RESULTS.glob(pattern)):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not payload.get("complete"):
            print(f"  경고: {path.name} 은 미완료 실행이다 (complete=false)")
        for author in payload["authors"]:
            author["site"] = payload.get("site", path.stem)
            rows.append(author)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pattern", default="final_train30_*.json")
    args = parser.parse_args()

    rows = load(args.pattern)
    if not rows:
        raise SystemExit(f"{args.pattern} 에 맞는 결과 파일이 없다.")

    conditions = tuple(rows[0]["conditions"])
    missing = [r for r in rows if tuple(r["conditions"]) != conditions]
    if missing:
        raise SystemExit("파일마다 조건이 다르다. 같은 조건으로 돌린 것만 합칠 것.")

    trains = {r["n_train"] for r in rows}
    tests = {len(r["per_document"][BASELINE]) for r in rows}
    print(f"저자 {len(rows)}명 | 학습 {sorted(trains)} | 홀드아웃 {sorted(tests)}")
    if len(trains) > 1 or len(tests) > 1:
        print("  경고: 저자마다 표본 크기가 다르다. 평균을 그대로 읽으면 안 된다.")

    print(f"\n=== 형식 거리 (낮을수록 이 저자에 가깝다) ===")
    print(f"{'저자':22}" + "".join(f"{c:>16}" for c in conditions))
    for row in rows:
        cells = "".join(f"{row['form_distance'][c]:16.3f}" for c in conditions)
        print(f"{row['site'] + '/u' + str(row['user_id']):22}{cells}")
    print(f"{'평균':22}" + "".join(
        f"{statistics.fmean(r['form_distance'][c] for r in rows):16.3f}" for c in conditions
    ))

    print(f"\n=== base 대비 형식 거리 개선 (저자 수와 부호검정) ===")
    print(f"{'조건':18}{'평균 형식거리':>14}{'개선폭':>10}{'이긴 저자':>11}{'p값':>9}")
    baseline_mean = statistics.fmean(r["form_distance"][BASELINE] for r in rows)
    for cond in conditions:
        mean = statistics.fmean(r["form_distance"][cond] for r in rows)
        wins = sum(
            1
            for r in rows
            if r["form_distance"][cond] < r["form_distance"][BASELINE]
        )
        p = sign_test_p(wins, len(rows)) if cond != BASELINE else 1.0
        print(f"{cond:18}{mean:14.3f}{baseline_mean - mean:+10.3f}"
              f"{wins:8d}/{len(rows):<3}{p:9.3f}")

    print(f"\n=== ROUGE-L (독립 지표) ===")
    print(f"{'조건':18}{'평균':>10}")
    for cond in conditions:
        print(f"{cond:18}{statistics.fmean(r['means'][cond] for r in rows):10.3f}")

    print(f"\n=== 길이 (홀드아웃 실제 대비 상대오차) ===")
    print(f"{'조건':18}{'평균오차':>10}")
    for cond in conditions:
        errors = [
            abs(r["achieved"][cond]["words_per_answer"]
                - r["holdout_stats"]["words_per_answer"])
            / max(r["holdout_stats"]["words_per_answer"], 1e-6)
            for r in rows
        ]
        print(f"{cond:18}{statistics.fmean(errors):10.3f}")

    print(f"\n=== 프롬프트 길이 (단어) ===")
    print(f"{'조건':18}{'중앙값':>10}{'최대':>8}")
    for cond in conditions:
        words = [r["prompt_words"][cond] for r in rows]
        print(f"{cond:18}{statistics.median(words):10.0f}{max(words):8d}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
