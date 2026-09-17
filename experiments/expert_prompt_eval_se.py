"""실제 저자 코퍼스에서 전문가 프롬프트를 홀드아웃 검증한다.

`experiments/expert_prompt_eval.py` 는 MACSum 페르소나로 잰다. 그 결과가
과제 유형에 의존하는 것이 드러났으므로(압축률 앵커는 요약의 산물이었다)
같은 방법을 **실제 사람**에게 대고 다시 재야 한다. 여기가 그 자리다.

**왜 이 코퍼스인가.** Stack Exchange 답변자 한 명은 제품이 노리는
사용자 그 자체다 - 자기 분야에 (질문, 답변) 쌍을 수십~수백 개 써둔 사람.
MACSum 페르소나는 사람이 속성 지시를 받아 쓴 것이라 문체가 균질했다
(글머리 기호 0, 문단 수 상수). 실제 저자는 문단 수 1.7~6.1, 글머리 기호
0~0.106 으로 갈린다.

**조건.**
  base        : 질문에 답하라는 지시만. 저자 정보 없음.
  stable      : 길이 모수화를 측정으로 고른 앵커 (`stable_length_anchor`).
  ratio_forced: 압축률로 강제한 앵커. 요약에서 이겼던 그 방법.
  paragraphs  : stable + 문단 수 목표. 판별력 진단을 통과한 유일한
                넓힌 지표라서, 갈리는 코퍼스에서 실제로 기여하는지 본다.

ratio_forced 를 넣는 이유: "측정으로 고른다"가 값을 하려면 잘못 고른
쪽보다 나아야 한다. 그게 아니면 모수화 선택은 장식이다.

**지표.** 형식 거리(주 지표)와 ROUGE-L(내용, 독립 채점자). Q&A 에서는
내용이 질문에 의해 거의 정해지므로 ROUGE-L 이 조건 간에 잘 안 움직일
수 있다 - 그러면 그대로 보고한다.

실행:
    python -m experiments.expert_prompt_eval_se --site cooking --train 12 --test 25
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

from dotenv import load_dotenv

from agents.expert_onboarding import (
    ExpertExample,
    anchor_text,
    corpus_stats,
    form_distance,
    length_parameterization,
    ratio_anchor,
    stable_length_anchor,
)
from engine.generator import generate_all_with_prompts
from experiments.expert_prompt_eval import sign_test_p
from experiments.independent_grader import rouge_l_score

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "stackexchange"
RESULTS = ROOT / "experiments" / "results"

MODEL = "openai/gpt-4.1-mini"

# 저자 정보를 하나도 담지 않은 과제 서술. 여기에 문체 힌트가 섞이면
# base 가 오염돼서 앵커의 기여를 잴 수 없다.
TASK_DESCRIPTION = (
    "Answer the following question from an online question-and-answer site. "
    "Write the answer only, with no preamble."
)

CONDITIONS = ("base", "stable", "ratio_forced", "paragraphs")


def load_corpus(site: str) -> dict:
    matches = sorted(CACHE.glob(f"{site}_a*_n*.json"))
    if not matches:
        raise SystemExit(
            f"{site} 코퍼스가 없다. 먼저 받을 것: "
            f"python -m experiments.expert_corpus_se --site {site}"
        )
    print(f"코퍼스: {matches[-1].relative_to(ROOT)}")
    return json.loads(matches[-1].read_text(encoding="utf-8"))


def author_examples(author: dict) -> list[ExpertExample]:
    return [
        ExpertExample(output=pair["answer"], task=pair["task"])
        for pair in author["pairs"]
    ]


def run_author(author: dict, n_train: int, n_test: int) -> dict:
    """저자 한 명에 대해 조건별로 홀드아웃 과제를 풀린다.

    분할은 캐시에 담긴 순서를 그대로 쓴다. 수집 시점에 득표순으로
    받았으므로 앞쪽이 인기 답변인데, 학습·홀드아웃이 체계적으로 달라지는
    문제는 MACSum 에서 이미 물렸다 - 그래서 여기서도 섞는다.
    """
    import random

    examples = author_examples(author)
    random.Random(0).shuffle(examples)
    if len(examples) < n_train + n_test:
        raise SystemExit(f"저자 {author['user_id']}: 쌍이 부족하다 ({len(examples)}개)")
    train, test = examples[:n_train], examples[n_train : n_train + n_test]

    kind, measured = length_parameterization(train)
    stats = corpus_stats(train)
    paragraph_target = stats.get("paragraphs_per_answer")
    print(f"\n저자 {author['user_id']} - 고른 모수화: {kind} {measured}")
    print(f"  학습 {len(train)}개 / 홀드아웃 {len(test)}개")
    print(f"  학습에서 잰 형식: {stats['words_per_answer']:.0f}단어 "
          f"/ {stats['sentences_per_answer']:.1f}문장 / {paragraph_target:.1f}문단")

    scores: dict[str, list[float]] = {name: [] for name in CONDITIONS}
    generated: dict[str, list[ExpertExample]] = {name: [] for name in CONDITIONS}

    for index, example in enumerate(test, start=1):
        stable_line, _, _ = stable_length_anchor(train, example.task)
        ratio_line = ratio_anchor(train, example.task)
        paragraph_line = (
            anchor_text({"paragraphs_per_answer": paragraph_target})
            if paragraph_target
            else ""
        )
        prompts = {
            "base": TASK_DESCRIPTION,
            "stable": _join(TASK_DESCRIPTION, stable_line),
            "ratio_forced": _join(TASK_DESCRIPTION, ratio_line),
            # 두 앵커 문장을 나란히 붙인다. stable 위에 문단 목표만
            # 더한 차이라서 문단 절의 기여가 그대로 분리된다.
            "paragraphs": _join(TASK_DESCRIPTION, stable_line, paragraph_line),
        }
        outputs = generate_all_with_prompts(
            [prompts[name] for name in CONDITIONS],
            example.task,
            model=MODEL,
            temperature=0.0,
        )
        line = []
        for name, output in zip(CONDITIONS, outputs):
            score = rouge_l_score(output, example.output)
            scores[name].append(score)
            generated[name].append(ExpertExample(output=output, task=example.task))
            line.append(f"{name} {score:.3f}")
        print(f"  홀드아웃 {index}/{len(test)}: " + " | ".join(line))

    means = {name: round(statistics.fmean(values), 3) for name, values in scores.items()}
    distances = {name: form_distance(generated[name], test) for name in CONDITIONS}
    achieved = {name: corpus_stats(generated[name]) for name in CONDITIONS}
    target_stats = corpus_stats(test)
    paired = {
        name: sum(1 for a, b in zip(scores[name], scores["base"]) if a > b)
        for name in CONDITIONS
        if name != "base"
    }

    return {
        "user_id": author["user_id"],
        "parameterization": kind,
        "cv": measured,
        "train_stats": stats,
        "holdout_stats": target_stats,
        "means": means,
        "form_distance": distances,
        "achieved": achieved,
        "paired_wins_vs_base": paired,
        "sign_test_p": {
            name: round(sign_test_p(wins, len(test)), 5) for name, wins in paired.items()
        },
        "per_document": scores,
    }


def _join(*parts: str) -> str:
    return "\n".join(part for part in parts if part)


def report(results: list[dict]) -> None:
    print("\n\n=== 저자별 요약 ===")
    print(f"{'저자':10}{'모수화':>10}" + "".join(f"{name:>14}" for name in CONDITIONS))
    for result in results:
        row = "".join(f"{result['means'][name]:14.3f}" for name in CONDITIONS)
        print(f"{'u' + str(result['user_id']):10}{result['parameterization']:>10}{row}")

    print(f"\n형식 거리 (낮을수록 이 저자에 가깝다)")
    print(f"{'저자':10}" + "".join(f"{name:>14}" for name in CONDITIONS))
    for result in results:
        row = "".join(f"{result['form_distance'][name]:14.3f}" for name in CONDITIONS)
        print(f"{'u' + str(result['user_id']):10}{row}")

    print(f"\n길이 (홀드아웃 실제 대비 생성 단어 수)")
    print(f"{'저자':10}{'실제':>10}" + "".join(f"{name:>14}" for name in CONDITIONS))
    for result in results:
        actual = result["holdout_stats"]["words_per_answer"]
        row = "".join(
            f"{result['achieved'][name]['words_per_answer']:14.0f}" for name in CONDITIONS
        )
        print(f"{'u' + str(result['user_id']):10}{actual:10.0f}{row}")

    print(f"\nbase 대비 페어드 승수 / 부호검정 p")
    for result in results:
        parts = [
            f"{name} {result['paired_wins_vs_base'][name]}승 p={result['sign_test_p'][name]:.3f}"
            for name in CONDITIONS
            if name != "base"
        ]
        print(f"  u{result['user_id']}: " + " | ".join(parts))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", default="cooking")
    parser.add_argument("--train", type=int, default=12)
    parser.add_argument("--test", type=int, default=25)
    parser.add_argument("--authors", type=int, default=None, help="앞에서 몇 명만 돌린다")
    args = parser.parse_args()

    corpus = load_corpus(args.site)
    authors = corpus["authors"][: args.authors] if args.authors else corpus["authors"]

    results = [run_author(author, args.train, args.test) for author in authors]
    report(results)

    RESULTS.mkdir(parents=True, exist_ok=True)
    out = RESULTS / f"expert_prompt_se_{args.site}.json"
    out.write_text(
        json.dumps({"site": args.site, "authors": results}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n결과 저장: {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
