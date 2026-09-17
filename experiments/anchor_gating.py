"""앵커를 붙일지 말지 미리 가를 수 있는가.

**문제.** 측정한 길이 앵커는 평균적으로 도움이 되지만 모든 저자에게
그렇지는 않다. cooking 저자 4명 중 한 명(u67)은 앵커를 붙였을 때 형식
거리가 0.189 에서 0.264 로 **아무것도 안 한 것보다 나빠졌다.** 그 저자만
학습 평균 212단어에 모델 기본 출력이 215단어였다 - 모델이 가만히 뒀을 때
이미 그 사람 길이로 쓰고 있었다.

**가설.** 저자와 모델 기본 출력의 길이 격차(`length_gap`)가 작으면
앵커가 도움이 안 되거나 해가 된다. 격차는 학습 자료와 학습 과제의 기본
출력만으로 구할 수 있으므로 홀드아웃을 보지 않고 판정할 수 있다.

**왜 저자 4명으로는 안 되는가.** 악화 사례가 하나뿐이라 그 한 점에
맞춰 임계값을 정하면 그냥 끼워맞추는 것이다. 네 사이트(cooking · writing ·
diy · academia) x 저자 4명 = 16명으로 늘려서 (격차, 이득) 관계를 실측한다.

**측정 방식.** 저자마다 base 와 stable 두 조건만 돌린다. 조건을 늘리면
호출이 배수로 늘고, 지금 답이 필요한 것은 "앵커가 이 저자에게 도움이
됐는가" 하나다.

  이득 = base 형식 거리 - stable 형식 거리   (양수면 앵커가 도움이 됨)

그다음 임계값을 훑어서, 격차가 임계값 미만인 저자에게 앵커를 빼면
전체 평균이 나아지는지 본다. 판정에 홀드아웃 값을 쓰지 않으므로
**실제로 쓸 수 있는 규칙**이다.

실행:
    python -m experiments.anchor_gating --test 15
    python -m experiments.anchor_gating --sites cooking --test 25
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from pathlib import Path

from dotenv import load_dotenv

from agents.expert_onboarding import (
    ExpertExample,
    corpus_stats,
    form_distance,
    length_gap,
    length_parameterization,
    stable_length_anchor,
)
from engine.generator import generate_all_with_prompts
from experiments.independent_grader import rouge_l_score

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "stackexchange"
RESULTS = ROOT / "experiments" / "results"

MODEL = "openai/gpt-4.1-mini"

# 다른 실험들과 같은 문구·같은 시드를 쓴다. 다르면 이미 캐시에 있는
# 생성 결과를 못 쓰고 수치도 나란히 놓을 수 없다.
TASK_DESCRIPTION = (
    "Answer the following question from an online question-and-answer site. "
    "Write the answer only, with no preamble."
)
SPLIT_SEED = 0

DEFAULT_SITES = ("cooking", "writing", "diy", "academia")

# 훑어볼 임계값. 실측된 격차가 0.014 ~ 0.66 구간에 퍼져 있어 그 범위를 덮는다.
THRESHOLDS = (0.0, 0.03, 0.05, 0.08, 0.10, 0.15, 0.20, 0.25, 0.30)


def load_site(site: str) -> list[dict]:
    matches = sorted(CACHE.glob(f"{site}_a*_n*.json"))
    if not matches:
        raise SystemExit(
            f"{site} 코퍼스가 없다. 먼저 받을 것: "
            f"python -m experiments.expert_corpus_se --site {site}"
        )
    return json.loads(matches[-1].read_text(encoding="utf-8"))["authors"]


def run_author(
    site: str, author: dict, n_train: int, n_test: int, holdout_offset: int | None = None
) -> dict:
    examples = [
        ExpertExample(output=pair["answer"], task=pair["task"])
        for pair in author["pairs"]
    ]
    random.Random(SPLIT_SEED).shuffle(examples)
    # 홀드아웃 시작 위치를 따로 줄 수 있다. 학습 크기를 바꾸면서 같은
    # 홀드아웃으로 비교하려면 이게 필요하다 - 기본값(학습 바로 뒤)으로
    # 두면 학습을 늘릴 때 홀드아웃도 밀려서 두 효과가 섞인다.
    offset = n_train if holdout_offset is None else holdout_offset
    if offset < n_train:
        raise SystemExit(f"홀드아웃 시작({offset})이 학습 크기({n_train})보다 앞이다")
    train, test = examples[:n_train], examples[offset : offset + n_test]
    if len(test) < n_test:
        raise SystemExit(
            f"저자 {author['user_id']}: 홀드아웃이 부족하다 "
            f"({len(test)}개, 필요 {n_test}개, 전체 {len(examples)}개)"
        )

    # 기본 출력은 **학습 과제**로 만든다. 홀드아웃으로 만들면 판정이
    # 정답을 엿본 셈이 되어 규칙이 실제로는 못 쓰는 것이 된다.
    default_outputs = [
        ExpertExample(
            output=generate_all_with_prompts(
                [TASK_DESCRIPTION], example.task, model=MODEL, temperature=0.0
            )[0],
            task=example.task,
        )
        for example in train
    ]

    gap = length_gap(train, default_outputs)
    kind, _ = length_parameterization(train)

    scores = {"base": [], "stable": []}
    generated = {"base": [], "stable": []}
    for example in test:
        stable_line, _, _ = stable_length_anchor(train, example.task)
        prompts = {
            "base": TASK_DESCRIPTION,
            "stable": TASK_DESCRIPTION + "\n" + stable_line,
        }
        outputs = generate_all_with_prompts(
            [prompts["base"], prompts["stable"]],
            example.task,
            model=MODEL,
            temperature=0.0,
        )
        for name, output in zip(("base", "stable"), outputs):
            scores[name].append(rouge_l_score(output, example.output))
            generated[name].append(ExpertExample(output=output, task=example.task))

    distances = {name: form_distance(generated[name], test) for name in generated}
    train_stats = corpus_stats(train)
    default_stats = corpus_stats(default_outputs)
    print(
        f"  u{author['user_id']:<8} 격차 {gap:.3f} "
        f"(저자 {train_stats['words_per_answer']:.0f}단어 / 기본 "
        f"{default_stats['words_per_answer']:.0f}단어) "
        f"| 형식거리 base {distances['base']:.3f} -> stable {distances['stable']:.3f} "
        f"| 이득 {distances['base'] - distances['stable']:+.3f}"
    )
    return {
        "site": site,
        "user_id": author["user_id"],
        "n_train": n_train,
        "holdout_offset": offset,
        "length_gap": gap,
        "parameterization": kind,
        "author_words": train_stats["words_per_answer"],
        "default_words": default_stats["words_per_answer"],
        "form_distance": distances,
        "gain": round(distances["base"] - distances["stable"], 4),
        "rouge_l": {
            name: round(statistics.fmean(values), 4) for name, values in scores.items()
        },
    }


def sweep(rows: list[dict]) -> list[dict]:
    """임계값마다, 격차가 그 아래인 저자에게 앵커를 빼면 어떻게 되는지.

    임계값 0.0 은 아무도 안 걸러내므로 항상 앵커를 붙이는 현재 동작이고,
    비교의 기준선이다.
    """
    out = []
    for threshold in THRESHOLDS:
        distances, gated = [], []
        for row in rows:
            skip = row["length_gap"] < threshold
            distances.append(row["form_distance"]["base" if skip else "stable"])
            if skip:
                gated.append(f"{row['site']}/u{row['user_id']}")
        out.append(
            {
                "threshold": threshold,
                "mean_form_distance": round(statistics.fmean(distances), 4),
                "gated_count": len(gated),
                "gated": gated,
            }
        )
    return out


def report(rows: list[dict]) -> None:
    print("\n\n=== 격차와 이득 (이득이 양수면 앵커가 도움이 됨) ===")
    print(f"{'저자':22}{'격차':>9}{'저자단어':>10}{'기본단어':>10}{'이득':>9}")
    for row in sorted(rows, key=lambda r: r["length_gap"]):
        print(
            f"{row['site'] + '/u' + str(row['user_id']):22}"
            f"{row['length_gap']:9.3f}{row['author_words']:10.0f}"
            f"{row['default_words']:10.0f}{row['gain']:+9.3f}"
        )

    for name in ("base", "stable"):
        print(f"\n{name} 평균 형식 거리: "
              f"{statistics.fmean(r['form_distance'][name] for r in rows):.4f}")

    hurt = [r for r in rows if r["gain"] < 0]
    helped = [r for r in rows if r["gain"] > 0]
    print(f"\n앵커가 도움이 된 저자 {len(helped)}명 / 해가 된 저자 {len(hurt)}명")
    if hurt and helped:
        print(f"  해가 된 저자의 격차: "
              f"{min(r['length_gap'] for r in hurt):.3f}~{max(r['length_gap'] for r in hurt):.3f}")
        print(f"  도움이 된 저자의 격차: "
              f"{min(r['length_gap'] for r in helped):.3f}~{max(r['length_gap'] for r in helped):.3f}")

    if len(rows) > 2:
        gaps = [r["length_gap"] for r in rows]
        gains = [r["gain"] for r in rows]
        if len(set(gaps)) > 1 and len(set(gains)) > 1:
            print(f"  상관(격차, 이득): {statistics.correlation(gaps, gains):.3f}")

    print("\n=== 임계값 스윕 (격차가 임계값 미만이면 앵커를 뺀다) ===")
    print(f"{'임계값':>8}{'평균 형식거리':>14}{'제외된 저자':>12}  누구")
    for entry in sweep(rows):
        who = ", ".join(entry["gated"][:4]) + ("..." if len(entry["gated"]) > 4 else "")
        print(f"{entry['threshold']:8.2f}{entry['mean_form_distance']:14.4f}"
              f"{entry['gated_count']:12d}  {who}")
    print("\n임계값 0.00 이 현재 동작(항상 붙임)이다. 그보다 낮아지는 구간이")
    print("있으면 게이팅이 값을 한다.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sites", nargs="*", default=list(DEFAULT_SITES))
    parser.add_argument("--train", type=int, default=12)
    parser.add_argument("--test", type=int, default=15)
    parser.add_argument(
        "--user-ids", nargs="*", type=int, default=None,
        help="이 저자들만 돌린다. 홀드아웃을 키워 특정 저자를 다시 볼 때 쓴다.",
    )
    parser.add_argument(
        "--holdout-offset", type=int, default=None,
        help="홀드아웃 시작 위치. 학습 크기를 바꾸며 같은 홀드아웃으로 비교할 때 쓴다.",
    )
    parser.add_argument("--out", default="anchor_gating.json")
    args = parser.parse_args()

    RESULTS.mkdir(parents=True, exist_ok=True)
    out = RESULTS / args.out

    def save(items: list[dict], complete: bool) -> None:
        out.write_text(
            json.dumps(
                {
                    "sites": args.sites,
                    "train": args.train,
                    "test": args.test,
                    "complete": complete,
                    "authors": items,
                    "sweep": sweep(items) if items else [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    rows: list[dict] = []
    for site in args.sites:
        print(f"\n[{site}]")
        for author in load_site(site):
            if args.user_ids and author["user_id"] not in args.user_ids:
                continue
            try:
                rows.append(
                    run_author(
                        site, author, args.train, args.test, args.holdout_offset
                    )
                )
            except Exception as error:  # noqa: BLE001 - 중단 사유를 남기고 끝낸다
                save(rows, complete=False)
                print(f"\n{site}/u{author['user_id']} 에서 중단: "
                      f"{type(error).__name__}: {error}")
                print(f"여기까지 저장: {out.relative_to(ROOT)} (저자 {len(rows)}명)")
                if rows:
                    report(rows)
                return 1
            save(rows, complete=False)

    save(rows, complete=True)
    report(rows)
    print(f"\n결과 저장: {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
