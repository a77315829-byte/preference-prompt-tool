"""요청한 길이와 실제로 나오는 길이의 전달 함수를 잰다.

왜 필요한가: 전문가 프롬프트 실험에서 수치 앵커가 목표처럼 작동하지 않았다.
128단어를 요청하면 98단어가, 170단어를 요청해도 99단어가 나왔다. 그런데
앵커를 아예 빼면 162단어를 쓴다. 요청값을 역보정하는 루프를 넣어도
안 움직였으므로, 앵커가 목표가 아니라 압축기처럼 작동한다는 가설이 남는다.

이 스크립트는 그 가설을 직접 시험한다. 같은 과제에 요청 단어 수만 바꿔
넣고 실제 산출 길이를 잰다. 결과가 단조 증가하면 앵커는 목표로 쓸 수
있고, 평평하면 쓸 수 없다.

실행:
    python -m experiments.length_transfer
    python -m experiments.length_transfer --tasks 5
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

from dotenv import load_dotenv

from agents.expert_onboarding import ExpertExample, corpus_stats
from engine.generator import generate_all_with_prompts

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
MACSUM_VAL = ROOT / "data" / "macsum" / "dataset" / "macdoc" / "val.json"
RESULTS = ROOT / "experiments" / "results"

MODEL = "openai/gpt-4.1-mini"
TASK_DESCRIPTION = "Summarise the given news article in English."

# 요청할 단어 수. 실측에서 앵커가 100단어 근방으로 몰리는 것처럼 보였으므로
# 그 아래위를 넓게 잡는다.
REQUESTED = (20, 40, 80, 120, 200, 320)


def _sources(count: int) -> list[str]:
    records = json.loads(MACSUM_VAL.read_text(encoding="utf-8"))
    return [" ".join(record["source"]) for record in records[:count]]


def run(task_count: int) -> dict:
    sources = _sources(task_count)
    print(f"과제 {len(sources)}개 x 요청값 {len(REQUESTED)}종 (앵커 없음 포함)\n")

    prompts = {"none": TASK_DESCRIPTION}
    for words in REQUESTED:
        sentences = max(1, round(words / 22))  # 문장당 22단어 가정
        prompts[str(words)] = (
            f"{TASK_DESCRIPTION}\n"
            f"Match this form: write about {sentences} sentences, "
            f"use roughly {words} words in total."
        )

    order = list(prompts)
    achieved: dict[str, list[ExpertExample]] = {name: [] for name in order}
    for index, source in enumerate(sources, start=1):
        outputs = generate_all_with_prompts(
            [prompts[name] for name in order], source, model=MODEL, temperature=0.0
        )
        for name, output in zip(order, outputs):
            achieved[name].append(ExpertExample(output=output, task=source))
        print(f"  과제 {index}/{len(sources)} 완료")

    print()
    print(f"{'요청':>6} {'실제 단어':>10} {'실제 문장':>10} {'요청/실제':>10}")
    table = {}
    for name in order:
        stats = corpus_stats(achieved[name])
        words = stats["words_per_answer"]
        table[name] = stats
        if name == "none":
            print(f"{'없음':>6} {words:10.1f} {stats['sentences_per_answer']:10.1f} {'-':>10}")
        else:
            ratio = words / int(name)
            print(f"{name:>6} {words:10.1f} {stats['sentences_per_answer']:10.1f} {ratio:10.2f}")

    lengths = [table[str(w)]["words_per_answer"] for w in REQUESTED]
    monotone = all(b >= a - 2 for a, b in zip(lengths, lengths[1:]))
    spread = max(lengths) - min(lengths)
    requested_spread = REQUESTED[-1] - REQUESTED[0]

    print()
    print(f"요청값 범위 {requested_spread}단어에 대해 실제 범위 {spread:.1f}단어")
    print(f"단조 증가: {monotone}")
    if spread < requested_spread * 0.3:
        print("판정: 앵커는 목표로 작동하지 않는다. 요청값을 크게 바꿔도 산출이 거의 안 움직인다.")
    elif monotone:
        print("판정: 앵커가 목표로 작동한다. 요청값을 올리면 산출도 올라간다.")
    else:
        print("판정: 단조롭지 않다. 구간별로 다르게 작동한다.")

    return {
        "model": MODEL,
        "task_count": len(sources),
        "requested": list(REQUESTED),
        "achieved_words": {name: table[name]["words_per_answer"] for name in order},
        "achieved_sentences": {name: table[name]["sentences_per_answer"] for name in order},
        "monotone": monotone,
        "achieved_spread": round(spread, 1),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", type=int, default=4)
    args = parser.parse_args()
    if not MACSUM_VAL.exists():
        raise SystemExit(f"MACSum 데이터가 없다: {MACSUM_VAL}")

    result = run(args.tasks)
    RESULTS.mkdir(parents=True, exist_ok=True)
    out = RESULTS / "length_transfer.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n결과 저장: {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
