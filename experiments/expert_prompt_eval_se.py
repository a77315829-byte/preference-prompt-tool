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
  selective   : stable + 모델 기본값과 실제로 다른 구조 항목만.
                paragraphs 가 문단은 맞추면서 길이·문장을 놓쳤으므로,
                이득이 있을 때만 더해서 상충을 피할 수 있는지 본다.
  fewshot     : 수치 없이 저자의 실제 답변 3개만 예시로 보여준다.
  fewshot_stable : 예시 + 길이 앵커. 앵커가 예시 위에 더할 게 있는지.

**fewshot 이 왜 반드시 있어야 하나.** "그냥 예시를 보여주면 되지 않나"가
가장 먼저 나올 질문이고, 그 비교 없이는 측정 앵커의 값어치를 주장할 수
없다. 이 조건은 앵커가 부딪힌 벽(수치 절을 쌓을수록 서로 간섭한다)도
우회한다 - 예시는 절이 아니라 본보기다. 다만 프롬프트가 수천 토큰
늘어나므로 이겼는지만이 아니라 얼마를 더 써서 이겼는지도 봐야 한다.

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
    fewshot_prompt,
    stable_length_anchor,
    structure_anchor,
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

CONDITIONS = (
    "base", "stable", "ratio_forced", "paragraphs", "selective",
    "fewshot", "fewshot_stable",
)


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

    # 모델이 가만히 뒀을 때 어떤 구조로 쓰는지를 **학습 과제**로 잰다.
    # 홀드아웃으로 재면 프롬프트가 정답을 엿본 셈이 된다.
    print(f"\n저자 {author['user_id']} - 모델 기본 출력 측정 중...")
    default_outputs = [
        ExpertExample(
            output=generate_all_with_prompts(
                [TASK_DESCRIPTION], example.task, model=MODEL, temperature=0.0
            )[0],
            task=example.task,
        )
        for example in examples[:n_train]
    ]

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
        selective_line, selected_keys = structure_anchor(
            train, default_outputs, example.task
        )
        # 예시는 과제마다 바뀌지 않지만, 조립을 한곳에 모아두면 조건이
        # 어떤 프롬프트를 받는지 한눈에 보인다.
        fewshot_line = fewshot_prompt(TASK_DESCRIPTION, train)
        prompts = {
            "base": TASK_DESCRIPTION,
            "stable": _join(TASK_DESCRIPTION, stable_line),
            "ratio_forced": _join(TASK_DESCRIPTION, ratio_line),
            # 두 앵커 문장을 나란히 붙인다. stable 위에 문단 목표만
            # 더한 차이라서 문단 절의 기여가 그대로 분리된다.
            "paragraphs": _join(TASK_DESCRIPTION, stable_line, paragraph_line),
            "selective": _join(TASK_DESCRIPTION, selective_line),
            "fewshot": fewshot_line,
            "fewshot_stable": _join(fewshot_line, stable_line),
        }
        if index == 1:
            print(f"  고른 구조 항목: {selected_keys or '없음'}")
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

    # 프롬프트 길이를 같이 남긴다. few-shot 이 이기더라도 비용이 몇 배인지
    # 모르면 제품 결정을 할 수 없다.
    prompt_words = {name: len(prompts[name].split()) for name in CONDITIONS}
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
        "selected_structure_keys": selected_keys,
        "model_default_stats": corpus_stats(default_outputs),
        "prompt_words": prompt_words,
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

    RESULTS.mkdir(parents=True, exist_ok=True)
    out = RESULTS / f"expert_prompt_se_{args.site}.json"

    def save(rows: list[dict], complete: bool) -> None:
        out.write_text(
            json.dumps(
                {"site": args.site, "complete": complete, "authors": rows},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    # 저자마다 바로 저장한다. 마지막에 한 번만 쓰다가 API 크레딧이 중간에
    # 끊겨 끝낸 저자들의 결과까지 같이 날렸다. 여기는 생성 캐시가 있어
    # 다시 돌리는 비용은 작지만, 중단 지점을 남기는 것 자체가 필요하다.
    results: list[dict] = []
    for author in authors:
        try:
            results.append(run_author(author, args.train, args.test))
        except Exception as error:  # noqa: BLE001 - 중단 사유를 남기고 끝낸다
            save(results, complete=False)
            print(f"\n저자 {author['user_id']} 에서 중단: "
                  f"{type(error).__name__}: {error}")
            print(f"여기까지 저장: {out.relative_to(ROOT)} (저자 {len(results)}명)")
            if results:
                report(results)
            return 1
        save(results, complete=False)

    save(results, complete=True)
    report(results)
    print(f"\n결과 저장: {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
