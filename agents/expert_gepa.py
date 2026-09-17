"""저자 프로필을 평가 함수로 만들어 GEPA 에게 프롬프트를 찾게 한다.

**왜 이 경로인가.** 수치 목표를 지시문 절로 쌓는 방식이 벽에 부딪혔다.
같은 현상이 세 번 나왔다.

  - 단어 수만 지시 → 모델이 문장을 잘게 쪼갠다 (문장당 13~17단어,
    저자는 18~23, 모델 기본값은 22.2).
  - 길이만 지시 → 문단이 붕괴한다 (저자 둘에서 1.0문단).
  - 길이·문장·문단을 같이 지시 → 앞의 둘이 덜 지켜진다 (형식 거리
    0.158 → 0.256, 아무것도 안 한 base 0.233 보다도 나쁘다).

모델 기본값과 다른 항목만 골라 붙이는 것으로도 안 됐다 - 실제 저자
4명 전원이 문단·글머리 기호에서 기본값과 달라 선별 게이트가 아예
작동하지 않았고 결과도 같았다(0.264).

즉 남은 문제는 "무엇을 재는가"가 아니라 **여러 수치 목표를 한 프롬프트에
쌓으면 서로 간섭한다**는 것이다. 문구를 사람이 조율하는 대신 최적화기가
찾게 하는 것이 맞고, 이 프로젝트에는 그 부품이 이미 있다 - GEPA 와
`engine/metric_builder.py` 계열의 (점수, 자연어 피드백) 평가 함수. 여기서는
축 선호 대신 **측정한 저자 프로필**을 평가 함수로 쓴다
(`agents.expert_onboarding.expert_form_metric`).

**규칙 10 을 지킨다.** `optimize/run_gepa.py` 를 고치지 않고 거기의
`MetricEvaluator` 만 가져다 쓴다. 기존 파이프라인은 그대로다.

**순환 논증을 조심해야 한다** (절대 규칙 7). GEPA 가 이 평가 함수로
최적화하므로, 결과를 같은 함수로만 채점하면 자기가 맞춘 것을 자기가
채점하는 구조다. 그래서 보고는 두 가지를 반드시 같이 낸다.

  - 형식 점수: 최적화한 지표다. 한 번도 안 보여준 과제에서 재지만,
    함수 자체는 같으므로 "최적화한 지표"라고 이름을 붙여 적는다.
  - ROUGE-L: 최적화 루프에 쓰이지 않는 독립 지표.

**저자 본인 점수를 기준선으로 같이 낸다.** 저자의 실제 답변을 자기
프로필로 채점하면 0.40~0.67 밖에 안 나온다 - 답변 하나는 자기 평균
주위에서 흔들리기 때문이다. 1.0 을 기준으로 읽으면 결과를 크게
과소평가한다.

다만 이것을 **상한이라고 부르면 틀린다.** 이 지표는 학습 평균과의
거리를 재므로, 평균에 딱 붙어서 쓰는 생성기는 평균 주위에서 흔들리는
실제 사람보다 높은 점수를 받는다 - 실측에서 stable 조건이 0.653 으로
저자 본인 0.451 을 넘었다. 그러니 이 값은 "사람 수준이 여기쯤"이라는
참조선이고, 그보다 높은 점수는 이상하지 않다.

실행:
    python -m agents.expert_gepa --site cooking --train 12 --test 25
    python -m agents.expert_gepa --site cooking --authors 1 --budget 20
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from pathlib import Path

from dotenv import load_dotenv
from gepa import optimize as gepa_optimize
from gepa.adapters.default_adapter.default_adapter import DefaultAdapter

from agents.expert_onboarding import (
    ExpertExample,
    PROFILE_KEYS,
    content_leakage,
    corpus_stats,
    topic_leakage,
    expert_form_metric,
    fewshot_prompt,
    form_distance,
    profile_targets,
    stable_length_anchor,
)
from engine.generator import generate_all_with_prompts
from experiments.independent_grader import rouge_l_score
from optimize.run_gepa import MetricEvaluator

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "stackexchange"
RESULTS = ROOT / "experiments" / "results"

MODEL = "openai/gpt-4.1-mini"

# 성찰 모델. CLAUDE.md 는 성찰만 강한 모델을 쓰라고 하지만, 기존
# 어블레이션이 같은 소형 모델로 rich 0.98 대 terse 0.44 를 냈으므로
# 비교 가능성을 위해 그때와 같은 구성을 유지한다.
REFLECTION_MODEL = "openai/gpt-4.1-mini"

# 저자당 평가 호출 예산.
DEFAULT_BUDGET = 60

# 후보를 채점할 valset 크기. 학습 예시 앞쪽을 쓴다.
#
# 이 값을 학습 크기(12)로 두면 GEPA 가 **아무것도 하지 못한다** - 실측
# 확인: 예산 12 로 돌렸을 때 반복 0 의 기준 평가에 12회를 다 써서
# 탐색 여지가 0 이었고, 시드 프롬프트가 그대로 돌아왔다. 기준 평가
# 비용이 valset 크기만큼이므로 작게 잡아야 후보를 여러 개 볼 수 있다.
VAL_SIZE = 6

TASK_DESCRIPTION = (
    "Answer the following question from an online question-and-answer site. "
    "Write the answer only, with no preamble."
)

# 비교 대상. GEPA 가 값을 하는지 알려면 사람이 손으로 만든 최고 조건과
# 나란히 놓아야 한다. 실측된 형식 거리 순서는
# base 0.233 > fewshot 0.201 > stable 0.158 > fewshot_stable 0.121 이다.
# 즉 이겨야 하는 상대는 stable 이 아니라 fewshot_stable 이다.
CONDITIONS = ("base", "stable", "fewshot", "fewshot_stable", "gepa")


def foreign_corpus(exclude_site: str) -> list[ExpertExample]:
    """주제 어휘를 가려낼 대조군. 다른 사이트의 저자 전원을 쓴다.

    왜 넉넉히 주는가: 대조군이 작으면 일반 영어 단어까지 "주제 어휘"로
    잡힌다. 실측에서 40개로 쟀을 때 순수 형식 앵커가 0.105 로 나왔고,
    세 사이트 전체(1,148개)로 키우니 0.000 이 됐다.
    """
    examples: list[ExpertExample] = []
    for path in sorted(CACHE.glob("*_a*_n*.json")):
        if path.name.startswith(f"{exclude_site}_"):
            continue
        corpus = json.loads(path.read_text(encoding="utf-8"))
        examples.extend(
            ExpertExample(output=pair["answer"], task=pair["task"])
            for author in corpus["authors"]
            for pair in author["pairs"]
        )
    return examples


def load_author_examples(site: str, index: int) -> tuple[int, list[ExpertExample]]:
    matches = sorted(CACHE.glob(f"{site}_a*_n*.json"))
    if not matches:
        raise SystemExit(
            f"{site} 코퍼스가 없다. 먼저 받을 것: "
            f"python -m experiments.expert_corpus_se --site {site}"
        )
    corpus = json.loads(matches[-1].read_text(encoding="utf-8"))
    author = corpus["authors"][index]
    examples = [
        ExpertExample(output=pair["answer"], task=pair["task"])
        for pair in author["pairs"]
    ]
    # 다른 실험과 같은 시드로 섞는다. 분할이 달라지면 수치를 나란히
    # 놓을 수 없다.
    random.Random(0).shuffle(examples)
    return author["user_id"], examples


def optimize_prompt(
    train: list[ExpertExample], budget: int, val_size: int = VAL_SIZE
) -> tuple[str, float]:
    """학습 과제만으로 프롬프트를 찾는다. 홀드아웃은 건드리지 않는다.

    시드는 저자 정보가 하나도 없는 과제 서술이다. 여기에 이미 앵커를
    넣어두면 시드가 지표에 대해 반쯤 최적화된 상태라 개선 여지가 사라진다
    - 피드백 풍부도 어블레이션 1차 시도에서 정확히 그렇게 무의미한
    비교가 나왔다.
    """
    metric = expert_form_metric(train)
    adapter = DefaultAdapter(model=MODEL, evaluator=MetricEvaluator(metric))
    trainset = [{"input": example.task} for example in train]
    # 성찰용 미니배치는 학습 전체에서 뽑고, 후보 채점은 앞쪽 일부로만
    # 한다. 채점 집합을 크게 잡으면 예산이 기준 평가에서 다 녹는다.
    valset = trainset[:val_size]

    result = gepa_optimize(
        seed_candidate={"system_prompt": TASK_DESCRIPTION},
        trainset=trainset,
        valset=valset,
        adapter=adapter,
        reflection_lm=REFLECTION_MODEL,
        max_metric_calls=budget,
        display_progress_bar=False,
    )
    return result.best_candidate["system_prompt"], result.val_aggregate_scores[
        result.best_idx
    ]


def evaluate(
    train: list[ExpertExample],
    test: list[ExpertExample],
    optimized: str,
) -> dict:
    """네 조건을 같은 홀드아웃 과제에 돌려 형식 점수와 ROUGE-L 을 낸다."""
    metric = expert_form_metric(train)
    fewshot = fewshot_prompt(TASK_DESCRIPTION, train)

    form_scores: dict[str, list[float]] = {name: [] for name in CONDITIONS}
    rouge: dict[str, list[float]] = {name: [] for name in CONDITIONS}
    generated: dict[str, list[ExpertExample]] = {name: [] for name in CONDITIONS}
    prompts_seen: dict[str, str] = {}

    for index, example in enumerate(test, start=1):
        stable_line, _, _ = stable_length_anchor(train, example.task)
        prompts = {
            "base": TASK_DESCRIPTION,
            "stable": TASK_DESCRIPTION + "\n" + stable_line,
            "fewshot": fewshot,
            "fewshot_stable": fewshot + "\n" + stable_line,
            "gepa": optimized,
        }
        prompts_seen = prompts
        outputs = generate_all_with_prompts(
            [prompts[name] for name in CONDITIONS],
            example.task,
            model=MODEL,
            temperature=0.0,
        )
        for name, output in zip(CONDITIONS, outputs):
            form_scores[name].append(metric(output, example.task)[0])
            rouge[name].append(rouge_l_score(output, example.output))
            generated[name].append(ExpertExample(output=output, task=example.task))
        if index % 5 == 0:
            print(f"    홀드아웃 {index}/{len(test)}")

    # 저자 본인의 답변을 자기 프로필로 채점한 값. 상한이 아니라 참조선이다
    # (평균에 붙는 생성기는 흔들리는 사람보다 높게 나온다).
    ceiling = statistics.fmean(metric(e.output, e.task)[0] for e in test)

    return {
        "ceiling_author_own": round(ceiling, 3),
        "form_score": {
            name: round(statistics.fmean(values), 3) for name, values in form_scores.items()
        },
        "rouge_l": {
            name: round(statistics.fmean(values), 3) for name, values in rouge.items()
        },
        "form_distance": {
            name: form_distance(generated[name], test) for name in CONDITIONS
        },
        "achieved": {name: corpus_stats(generated[name]) for name in CONDITIONS},
        "prompt_words": {name: len(prompts_seen[name].split()) for name in CONDITIONS},
        "per_document_form": form_scores,
    }


def run_author(site: str, index: int, n_train: int, n_test: int, budget: int) -> dict:
    user_id, examples = load_author_examples(site, index)
    if len(examples) < n_train + n_test:
        raise SystemExit(f"저자 {user_id}: 쌍이 부족하다 ({len(examples)}개)")
    train, test = examples[:n_train], examples[n_train : n_train + n_test]

    print(f"\n저자 {user_id} - GEPA 최적화 중 (예산 {budget}회)...")
    print(f"  프로필 목표(첫 과제): "
          f"{ {k: round(v, 2) for k, v in profile_targets(train, test[0].task).items()} }")
    optimized, train_score = optimize_prompt(train, budget)
    if optimized.strip() == TASK_DESCRIPTION.strip():
        print("  경고: GEPA 가 시드를 그대로 돌려줬다 - 예산이 부족한지 확인할 것.")
    print(f"  학습 점수 {train_score:.3f}, 찾은 프롬프트 {len(optimized.split())}단어")
    print(f"  --- 찾은 프롬프트 ---\n{optimized}\n  ---")

    result = evaluate(train, test, optimized)
    # 찾아준 프롬프트가 학습 자료를 얼마나 베꼈는지 코드로 잰다.
    # base·stable 은 0 이어야 하고, GEPA 쪽이 높으면 산출물을 "문체
    # 프롬프트"라고 부를 수 없다.
    #
    # 두 가지를 따로 잰다. 축자 겹침만 보면 GEPA 를 놓친다 - 실측에서
    # GEPA 프롬프트의 4-gram 겹침은 0.000 이었고(few-shot 은 0.959),
    # 베낀 게 아니라 자기 말로 다시 쓴 것이었다. 주제 어휘 쪽에서
    # 0.031 로 잡힌다.
    foreign = foreign_corpus(site)
    fewshot_text = fewshot_prompt(TASK_DESCRIPTION, train)
    result["leakage"] = {
        "foreign_corpus_size": len(foreign),
        "verbatim": {
            "base": content_leakage(TASK_DESCRIPTION, train),
            "fewshot": content_leakage(fewshot_text, train),
            "gepa": content_leakage(optimized, train),
        },
        "topic_vocabulary": {
            "base": topic_leakage(TASK_DESCRIPTION, train, foreign),
            "fewshot": topic_leakage(fewshot_text, train, foreign),
            "gepa": topic_leakage(optimized, train, foreign),
        },
    }
    result["user_id"] = user_id
    result["train_score"] = round(float(train_score), 3)
    result["optimized_prompt"] = optimized
    return result


def report(results: list[dict]) -> None:
    print("\n\n=== 형식 점수 (GEPA 가 최적화한 지표 - 순환 주의) ===")
    print(f"{'저자':10}{'저자본인(참조선)':>18}" + "".join(f"{n:>12}" for n in CONDITIONS))
    for r in results:
        row = "".join(f"{r['form_score'][n]:12.3f}" for n in CONDITIONS)
        print(f"u{r['user_id']:<9}{r['ceiling_author_own']:18.3f}{row}")

    print("\n=== ROUGE-L (독립 지표) ===")
    print(f"{'저자':10}" + "".join(f"{n:>12}" for n in CONDITIONS))
    for r in results:
        print(f"u{r['user_id']:<9}" + "".join(f"{r['rouge_l'][n]:12.3f}" for n in CONDITIONS))

    print("\n=== 형식 거리 (길이·문장, 낮을수록 좋다) ===")
    print(f"{'저자':10}" + "".join(f"{n:>12}" for n in CONDITIONS))
    for r in results:
        print(f"u{r['user_id']:<9}" + "".join(f"{r['form_distance'][n]:12.3f}" for n in CONDITIONS))

    print("\n=== 프롬프트 길이 (단어) ===")
    print(f"{'저자':10}" + "".join(f"{n:>12}" for n in CONDITIONS))
    for r in results:
        print(f"u{r['user_id']:<9}" + "".join(f"{r['prompt_words'][n]:12d}" for n in CONDITIONS))

    print("\n=== 평균 ===")
    for label, key in (("형식 점수", "form_score"), ("ROUGE-L", "rouge_l"),
                       ("형식 거리", "form_distance")):
        means = {n: statistics.fmean(r[key][n] for r in results) for n in CONDITIONS}
        print(f"  {label:10}" + "  ".join(f"{n}={means[n]:.3f}" for n in CONDITIONS))
    print(f"  {'참조선':10}저자 본인 평균="
          f"{statistics.fmean(r['ceiling_author_own'] for r in results):.3f}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", default="cooking")
    parser.add_argument("--train", type=int, default=12)
    parser.add_argument("--test", type=int, default=25)
    parser.add_argument("--authors", type=int, default=4)
    parser.add_argument("--budget", type=int, default=DEFAULT_BUDGET)
    args = parser.parse_args()

    RESULTS.mkdir(parents=True, exist_ok=True)
    out = RESULTS / f"expert_gepa_{args.site}.json"

    def save(rows: list[dict], complete: bool) -> None:
        out.write_text(
            json.dumps(
                {
                    "site": args.site,
                    "budget": args.budget,
                    "profile_keys": list(PROFILE_KEYS),
                    "complete": complete,
                    "authors_requested": args.authors,
                    "authors": rows,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    # **저자마다 바로 저장한다.** 마지막에 한 번만 쓰다가 실제로 물렸다 -
    # API 크레딧이 중간에 끊겨 저자 2명분의 최적화(호출 120회, 실제
    # 비용)가 디스크에 하나도 안 남았다. 중단은 언제든 일어나고, GEPA
    # 최적화는 생성 캐시를 타지 않아 다시 돌리면 그 돈을 또 쓴다.
    results: list[dict] = []
    for index in range(args.authors):
        try:
            results.append(
                run_author(args.site, index, args.train, args.test, args.budget)
            )
        except Exception as error:  # noqa: BLE001 - 중단 사유를 남기고 끝낸다
            save(results, complete=False)
            print(f"\n{index + 1}번째 저자에서 중단: {type(error).__name__}: {error}")
            print(f"여기까지 저장: {out.relative_to(ROOT)} (저자 {len(results)}명)")
            if results:
                report(results)
            return 1
        save(results, complete=False)
        print(f"  저장 완료 (저자 {len(results)}명까지)")

    save(results, complete=True)
    report(results)
    print(f"\n결과 저장: {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
